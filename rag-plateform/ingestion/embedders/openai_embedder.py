from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from openai_client import build_openai_client

logger = logging.getLogger(__name__)


@dataclass
class OpenAIEmbedder:
    api_key: str
    model: str
    batch_size: int = 32
    dimensions: int | None = None
    client: Any = None

    def __post_init__(self):
        if self.client is None:
            self.client = build_openai_client(self.api_key)

    @classmethod
    def from_settings(cls, settings) -> "OpenAIEmbedder":
        return cls(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )

    def is_available(self) -> bool:
        return bool(self.api_key and self.client is not None)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.is_available():
            raise RuntimeError("OpenAI embedder non configure.")

        cleaned = [text.strip() for text in texts if text and text.strip()]
        if len(cleaned) != len(texts):
            raise ValueError("Impossible de generer des embeddings pour des chunks vides.")

        vectors: list[list[float]] = []
        for batch in self._iter_batches(cleaned):
            params = {
                "model": self.model,
                "input": batch,
                "encoding_format": "float",
            }
            if self.dimensions is not None:
                params["dimensions"] = self.dimensions

            response = self.client.embeddings.create(**params)
            vectors.extend(item.embedding for item in response.data)

        return vectors

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]

    def _iter_batches(self, items: Iterable[str]) -> Iterable[list[str]]:
        batch: list[str] = []
        for item in items:
            batch.append(item)
            if len(batch) >= self.batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
