from __future__ import annotations

from pathlib import Path

from config.settings import settings
from ingestion.embedders.openai_embedder import OpenAIEmbedder
from pipeline import load_documents_config
from retrieval.vector_store import QdrantVectorStore, SearchHit


class Retriever:
    def __init__(
        self,
        *,
        embedder: OpenAIEmbedder | None = None,
        vector_store: QdrantVectorStore | None = None,
    ):
        self.embedder = embedder or OpenAIEmbedder.from_settings(settings)
        self.vector_store = vector_store or QdrantVectorStore.from_settings(settings)

    def retrieve(self, *, collection_name: str, query: str, limit: int = 5) -> list[SearchHit]:
        query_vector = self.embedder.embed_query(query)
        return self.vector_store.query(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
        )

    def retrieve_for_domain(self, *, domain: str, query: str, limit: int = 5) -> list[SearchHit]:
        query_vector = self.embedder.embed_query(query)
        hits: list[SearchHit] = []

        for collection_name in self.resolve_collection_names(domain):
            hits.extend(
                self.vector_store.query(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=limit,
                )
            )

        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]

    def build_prompt(self, *, domain: str, question: str, hits: list[SearchHit]) -> str:
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
            collection_name = doc.get("collection") or doc.get("metadata", {}).get("domaine") or domain
            if collection_name not in seen:
                seen.add(collection_name)
                collections.append(collection_name)

        return collections or [domain]

    @staticmethod
    def _format_context(hits: list[SearchHit]) -> str:
        parts: list[str] = []
        for index, hit in enumerate(hits, start=1):
            metadata = hit.payload.get("metadata", {})
            article_id = metadata.get("article_id", "article inconnu")
            text = hit.payload.get("text", "")
            parts.append(f"[{index}] {article_id}\n{text}")
        return "\n\n".join(parts)
