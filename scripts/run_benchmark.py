"""
Run the retrieval+generation pipeline against a domain benchmark and save results.

Usage:
    python scripts/run_benchmark.py --domain droit_etranger
    python scripts/run_benchmark.py --domain droit_etranger --dry-run          # retrieval only, no LLM call
    python scripts/run_benchmark.py --domain droit_etranger --theme asile
    python scripts/run_benchmark.py --domain droit_etranger --difficulte simple
    python scripts/run_benchmark.py --domain droit_etranger --rerank-top-k 20              # rerank score (gratuit)
    python scripts/run_benchmark.py --domain droit_etranger --rerank-top-k 20 --rerank-backend cross_encoder

Architecture :
    retrieve_for_domain()  → ~400-500 chunks  (mesurés par score_benchmark.py)
         ↓ reranker
    top K chunks           → passés au LLM    (réduit les coûts de génération)

Output: data/benchmark/<domain>/<run_id>.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))

from config.settings import settings
from generation.openai_responder import OpenAIResponder
from retrieval.reranker import Reranker
from retrieval.retriever import Retriever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_benchmark(domain: str) -> dict:
    path = PROJECT_ROOT / "domains" / domain / "benchmark.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Aucun benchmark.yaml trouvé pour le domaine '{domain}' ({path})")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["benchmark"]


def run(
    *,
    domain: str,
    dry_run: bool,
    theme_filter: str | None,
    difficulte_filter: str | None,
    limit: int,
    rerank_top_k: int | None,
    rerank_backend: str,
) -> Path:
    benchmark = load_benchmark(domain)
    questions = benchmark["questions"]

    if theme_filter:
        questions = [q for q in questions if q["theme"] == theme_filter]
    if difficulte_filter:
        questions = [q for q in questions if q["difficulte"] == difficulte_filter]

    if not questions:
        logger.warning("Aucune question ne correspond aux filtres fournis.")
        sys.exit(0)

    retriever = Retriever()
    responder = OpenAIResponder.from_settings(settings) if not dry_run else None

    # Reranker — uniquement si --rerank-top-k est fourni
    reranker = None
    if rerank_top_k is not None:
        reranker = Reranker(backend=rerank_backend)
        logger.info(
            f"Reranker activé : backend={reranker.backend}, top_k={rerank_top_k}"
        )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = PROJECT_ROOT / "data" / "benchmark" / domain
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{run_id}.jsonl"

    logger.info(
        f"Benchmark '{domain}' — {len(questions)} question(s) | "
        f"dry_run={dry_run} | rerank_top_k={rerank_top_k} | output={output_path}"
    )

    with output_path.open("w", encoding="utf-8") as out:
        for i, q in enumerate(questions, 1):
            qid = q["id"]
            question_text = q["question"]
            logger.info(f"[{i}/{len(questions)}] {qid} — {question_text[:60]}…")

            # ── Retrieval (tous les chunks — mesurés par score_benchmark.py) ──
            hits_all = retriever.retrieve_for_domain(
                domain=domain,
                query=question_text,
                limit=limit,
            )

            # ── Reranking (sous-ensemble pour la génération) ──────────────────
            hits_for_generation = hits_all
            if reranker is not None and rerank_top_k is not None:
                hits_for_generation = reranker.rerank(
                    query=question_text,
                    hits=hits_all,
                    top_k=rerank_top_k,
                )

            prompt = retriever.build_prompt(
                domain=domain,
                question=question_text,
                hits=hits_for_generation,
            )

            # retrieved_chunks = TOUS les chunks (pour le scoring de recall)
            retrieved_chunks = [
                {
                    "score": round(hit.score, 6),
                    "article_id": hit.payload.get("metadata", {}).get("article_id", "inconnu"),
                    "text": hit.payload.get("text", ""),
                }
                for hit in hits_all
            ]

            # generation_chunks = chunks effectivement passés au LLM
            generation_chunks = [
                {
                    "score": round(hit.score, 6),
                    "article_id": hit.payload.get("metadata", {}).get("article_id", "inconnu"),
                    "text": hit.payload.get("text", ""),
                }
                for hit in hits_for_generation
            ] if reranker is not None else None

            answer = None
            if responder is not None:
                try:
                    answer = responder.answer(prompt)
                except Exception as exc:
                    logger.error(f"[{qid}] Erreur génération : {exc}")
                    answer = f"ERREUR: {exc}"

            record = {
                "run_id": run_id,
                "domain": domain,
                "id": qid,
                "theme": q["theme"],
                "difficulte": q["difficulte"],
                "question": question_text,
                "attente_minimale": q.get("attente_minimale", ""),
                "articles_cibles": q.get("articles_cibles", []),
                "retrieved_chunks": retrieved_chunks,       # TOUS → score recall
                "generation_chunks": generation_chunks,     # sous-ensemble → LLM
                "rerank_backend": reranker.backend if reranker else None,
                "rerank_top_k": rerank_top_k,
                "answer": answer,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"Résultats sauvegardés → {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exécute le benchmark retrieval/génération d'un domaine.")
    parser.add_argument("--domain", default="droit_etranger", help="Domaine cible (défaut: droit_etranger)")
    parser.add_argument("--dry-run", action="store_true", help="Retrieval uniquement, sans appel LLM")
    parser.add_argument("--theme", default=None, help="Filtrer par thème (ex: asile)")
    parser.add_argument("--difficulte", default=None, choices=["simple", "moyen", "difficile"],
                        help="Filtrer par niveau de difficulté")
    parser.add_argument("--limit", type=int, default=50,
                        help="Nombre de chunks récupérés par question (défaut: 50)")
    parser.add_argument("--rerank-top-k", type=int, default=None,
                        help="Nb de chunks conservés après reranking pour la génération (ex: 20). "
                             "Sans cette option, tous les chunks sont passés au LLM.")
    parser.add_argument("--rerank-backend", default="score",
                        choices=["score", "cross_encoder"],
                        help="Backend de reranking : 'score' (RRF, gratuit) ou "
                             "'cross_encoder' (multilingue, ~100ms, 0 coût API). Défaut: score")
    args = parser.parse_args()

    output_path = run(
        domain=args.domain,
        dry_run=args.dry_run,
        theme_filter=args.theme,
        difficulte_filter=args.difficulte,
        limit=args.limit,
        rerank_top_k=args.rerank_top_k,
        rerank_backend=args.rerank_backend,
    )
    print(f"\nFichier de résultats : {output_path}")


if __name__ == "__main__":
    main()
