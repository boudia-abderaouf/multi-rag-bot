from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from pipeline import load_documents_config

logger = logging.getLogger(__name__)


@dataclass
class RetrievalMetrics:
    query: str
    n_results: int
    latency_ms: float
    used_expansion: bool
    used_hyde: bool
    used_reranking: bool
    n_variants: int


@dataclass
class BenchmarkResult:
    total_queries: int
    recall_at_k: float
    precision_at_k: float
    mrr: float
    mean_latency_ms: float
    p95_latency_ms: float
    k: int
    details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            f"recall@{self.k}": round(self.recall_at_k, 4),
            f"precision@{self.k}": round(self.precision_at_k, 4),
            "mrr": round(self.mrr, 4),
            "mean_latency_ms": round(self.mean_latency_ms, 1),
            "p95_latency_ms": round(self.p95_latency_ms, 1),
            "k": self.k,
            "passes_80pct_threshold": (
                self.recall_at_k >= 0.80 and self.precision_at_k >= 0.80
            ),
        }

    def report(self) -> str:
        d = self.to_dict()
        status = "OK" if d["passes_80pct_threshold"] else "FAIL"
        sep = "=" * 62
        lines = [
            sep,
            "  BENCHMARK REPORT - Retriever Qdrant ameliore",
            sep,
            f"  Total queries         : {d['total_queries']}",
            f"  Recall@{self.k:<2}             : {self.recall_at_k:.2%}",
            f"  Precision@{self.k:<2}          : {self.precision_at_k:.2%}",
            f"  MRR                   : {self.mrr:.4f}",
            f"  Latence moyenne       : {d['mean_latency_ms']:.1f} ms",
            f"  Latence P95           : {d['p95_latency_ms']:.1f} ms",
            f"  Critere >= 80%        : {status}",
            sep,
        ]
        return "\n".join(lines)


# RRF constant — higher = less aggressive rank fusion
_RRF_K = 60


class Retriever:
    def __init__(
        self,
        *,
        embedder=None,
        vector_store=None,
    ):
        from config.settings import settings
        from ingestion.embedders.openai_embedder import OpenAIEmbedder
        from retrieval.vector_store import QdrantVectorStore

        self.embedder = embedder or OpenAIEmbedder.from_settings(settings)
        self.vector_store = vector_store or QdrantVectorStore.from_settings(settings)

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(self, *, collection_name: str, query: str, limit: int = 5):
        query_vector = self.embedder.embed_query(query)
        return self.vector_store.query(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
        )

    def retrieve_for_domain(
        self,
        *,
        domain: str,
        query: str,
        limit: int = 10,
        n_query_variants: int = 5,
        n_hyde: int = 3,
        direct_top_k: int = 100,
    ):
        """Multi-query retrieval fused with Reciprocal Rank Fusion + direct guarantee.

        Pipeline:
          1. Original query (verbatim)
          2. n_query_variants legal reformulations via LLM
          3. n_hyde HyDE documents from different angles
        All lists are merged with Reciprocal Rank Fusion.

        Additionally, the top `direct_top_k` hits from the original query are
        always included in the final result set.  This prevents articles that are
        highly relevant to the original query but poorly represented across
        variants/HyDE from being lost in the RRF merge.
        """
        candidate_limit = max(limit * 8, 400)

        queries = [query]
        if n_query_variants > 0 and self.embedder.is_available():
            queries.extend(self._expand_query(query, n_variants=n_query_variants))

        # HyDE: embed hypothetical CESEDA articles rather than the raw question.
        # Multiple angles cover both "définition" and "procédure" aspects.
        if n_hyde > 0 and self.embedder.is_available():
            for hyde_text in self._generate_hyde_multi(query, n=n_hyde):
                queries.append(hyde_text)

        collection_names = self.resolve_collection_names(domain)
        all_ranked_lists = []
        direct_hits: list = []  # top hits from the original query (index 0)

        for q_idx, q in enumerate(queries):
            query_vector = self.embedder.embed_query(q)
            hits_for_query = []
            for collection_name in collection_names:
                hits_for_query.extend(
                    self.vector_store.query(
                        collection_name=collection_name,
                        query_vector=query_vector,
                        limit=candidate_limit,
                    )
                )
            # deduplicate by point_id, keep highest score
            seen: dict = {}
            for h in hits_for_query:
                if h.point_id not in seen or h.score > seen[h.point_id].score:
                    seen[h.point_id] = h
            ranked = sorted(seen.values(), key=lambda x: x.score, reverse=True)
            all_ranked_lists.append(ranked[:candidate_limit])
            if q_idx == 0:
                # Keep a deep pool from the original query for the direct guarantee
                direct_hits = ranked[:max(direct_top_k, candidate_limit)]

        # Use candidate_limit for the RRF merge (not just `limit`) so that articles
        # appearing in the top pool of HyDE / variant queries — but NOT in the top pool
        # of the original query — are still surfaced.  This trades a small amount of
        # precision for significantly better recall on semantically-distant articles.
        rrf_results = self._rrf_merge(all_ranked_lists, limit=candidate_limit)

        # Hybrid guarantee: the top `direct_top_k` hits from the original query are
        # APPENDED to the RRF result set (not filtered back to `limit`).
        # This guarantees that any article in the top-`direct_top_k` direct-cosine
        # results is surfaced even if the multi-query RRF would have ranked it out.
        # Callers that need a hard cap should slice the result themselves.
        seen_ids = {h.point_id for h in rrf_results}
        # Use all direct hits up to candidate_limit (not capped to direct_top_k)
        # so that articles at high rank in the original query are guaranteed.
        extras = [h for h in direct_hits if h.point_id not in seen_ids]
        return rrf_results + extras

    def build_prompt(self, *, domain: str, question: str, hits) -> str:
        template_path = Path("domains") / domain / "prompt_template.txt"
        template = template_path.read_text(encoding="utf-8")
        context = self._format_context(hits)
        return template.format(context=context, question=question)

    @staticmethod
    def resolve_collection_names(domain: str) -> list[str]:
        try:
            documents = load_documents_config(domain)
        except FileNotFoundError:
            return [domain]

        collections: list[str] = []
        seen: set[str] = set()
        for doc in documents:
            name = doc.get("collection") or doc.get("metadata", {}).get("domaine") or domain
            if name not in seen:
                seen.add(name)
                collections.append(name)
        return collections or [domain]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _generate_hyde_multi(self, query: str, n: int = 2) -> list[str]:
        """HyDE – Hypothetical Document Embeddings, multiple angles.

        Generates n hypothetical CESEDA articles from different perspectives:
        - angle 0 : définition / déclaratif (qu'est-ce que c'est, qui est concerné)
        - angle 1 : procédure / conditions (comment ça s'applique, quelles règles)
        - angle 2 : effets juridiques / droits conférés / interdictions
        Legal articles use different vocabulary than questions; embedding realistic
        article excerpts bridges this gap far better than embedding the question.
        """
        angles = [
            (
                "Tu es rédacteur du CESEDA. Rédige un court extrait d'article (3-5 phrases) "
                "en style juridique officiel qui DÉFINIT ou DÉCRIT qui est concerné par la "
                "notion evoquée dans la question. Commence directement par le contenu, "
                "sans numéro d'article, en utilisant le vocabulaire exact du code.\n\nQuestion : "
            ),
            (
                "Tu es rédacteur du CESEDA. Rédige un court extrait d'article (3-5 phrases) "
                "en style juridique officiel qui FIXE LES CONDITIONS ou LA PROCÉDURE "
                "applicable au cas évoqué dans la question. Tournures passives, références "
                "aux autorités compétentes. Commence directement par le contenu, sans numéro "
                "d'article.\n\nQuestion : "
            ),
            (
                "Tu es rédacteur du CESEDA. Rédige un court extrait d'article (3-5 phrases) "
                "en style juridique officiel qui ÉTABLIT LES EFFETS JURIDIQUES, LES DROITS "
                "CONFÉRÉS ou les INTERDICTIONS applicables à la situation évoquée dans la question. "
                "Utilise des formulations comme 'emporte le droit de', 'ne peut faire l\\'objet de', "
                "'vaut autorisation de', 'donne lieu à'. Vocabulaire exact du CESEDA, sans numéro "
                "d'article.\n\nQuestion : "
            ),
        ]
        results = []
        client = self.embedder.client
        if client is None:
            return results
        for i, prefix in enumerate(angles[:n]):
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[{"role": "user", "content": prefix + query}],
                    max_tokens=250,
                    temperature=0.1,
                )
                content = (response.choices[0].message.content or "").strip()
                if content:
                    results.append(content)
            except Exception as exc:
                logger.warning(f"HyDE angle {i} failed: {exc}")
        return results

    def _generate_hyde(self, query: str) -> str | None:
        """Single HyDE — kept for backwards-compat; use _generate_hyde_multi instead."""
        results = self._generate_hyde_multi(query, n=1)
        return results[0] if results else None

    def _expand_query(self, query: str, n_variants: int = 2) -> list[str]:
        """Ask the LLM for alternative legal formulations of the query."""
        try:
            client = self.embedder.client
            if client is None:
                return []
            prompt = (
                f"Tu es un expert en droit des étrangers français (CESEDA). "
                f"Génère {n_variants} reformulations courtes et précises de cette question juridique "
                f"en utilisant le vocabulaire du Code de l'entrée et du séjour des étrangers. "
                f"Réponds UNIQUEMENT avec les reformulations, une par ligne, sans numérotation.\n\n"
                f"Question : {query}"
            )
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3,
            )
            content = response.choices[0].message.content or ""
            variants = [line.strip() for line in content.strip().splitlines() if line.strip()]
            return variants[:n_variants]
        except Exception as exc:
            logger.warning(f"Query expansion failed, falling back to single query: {exc}")
            return []

    @staticmethod
    def _rrf_merge(ranked_lists, *, limit: int):
        """Reciprocal Rank Fusion over multiple ranked hit lists."""
        from retrieval.vector_store import SearchHit

        rrf_scores: dict[str, float] = {}
        hit_by_id: dict[str, Any] = {}

        for ranked_list in ranked_lists:
            for rank, hit in enumerate(ranked_list, start=1):
                rrf_scores[hit.point_id] = (
                    rrf_scores.get(hit.point_id, 0.0) + 1.0 / (_RRF_K + rank)
                )
                if hit.point_id not in hit_by_id:
                    hit_by_id[hit.point_id] = hit

        top_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:limit]
        return [
            SearchHit(
                score=rrf_scores[pid],
                payload=hit_by_id[pid].payload,
                point_id=pid,
            )
            for pid in top_ids
        ]

    @staticmethod
    def _format_context(hits) -> str:
        parts: list[str] = []
        for index, hit in enumerate(hits, start=1):
            metadata = hit.payload.get("metadata", {})
            article_id = metadata.get("article_id", "article inconnu")
            text = hit.payload.get("text", "")
            parts.append(f"[{index}] {article_id}\n{text}")
        return "\n\n".join(parts)
