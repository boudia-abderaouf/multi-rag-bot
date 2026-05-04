from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient, models
except ImportError:  # pragma: no cover - depends on optional dependency
    QdrantClient = None
    models = None


@dataclass
class SearchHit:
    score: float
    payload: dict[str, Any]
    point_id: str


class QdrantVectorStore:
    def __init__(self, url: str, api_key: str = "", client: Any = None):
        self.url = url
        self.api_key = api_key
        self.client = client
        if self.client is None and QdrantClient is not None and url:
            kwargs = {"url": url}
            if api_key:
                kwargs["api_key"] = api_key
            self.client = QdrantClient(**kwargs)

    @classmethod
    def from_settings(cls, settings) -> "QdrantVectorStore":
        return cls(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    def is_available(self) -> bool:
        return bool(self.url and self.client is not None and models is not None)

    def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info(f"[{collection_name}] Collection Qdrant creee ({vector_size} dimensions).")

    def replace_document(
        self,
        *,
        collection_name: str,
        doc_id: str,
        records: list[dict[str, Any]],
        vectors: list[list[float]],
    ) -> None:
        if not self.is_available():
            raise RuntimeError("Qdrant n'est pas configure.")
        if not records:
            return
        if len(records) != len(vectors):
            raise ValueError("Le nombre de chunks et de vecteurs ne correspond pas.")

        self.ensure_collection(collection_name, len(vectors[0]))
        self.delete_document(collection_name=collection_name, doc_id=doc_id)

        points = []
        for record, vector in zip(records, vectors, strict=True):
            payload = {
                "doc_id": record["doc_id"],
                "chunk_id": record["chunk_id"],
                "chunk_index": record["chunk_index"],
                "document_name": record["document_name"],
                "collection": record["collection"],
                "text": record["text"],
                "metadata": record["metadata"],
            }
            points.append(
                models.PointStruct(
                    id=self.build_point_id(doc_id=doc_id, chunk_index=record["chunk_index"]),
                    vector=vector,
                    payload=payload,
                )
            )

        self.client.upsert(collection_name=collection_name, wait=True, points=points)

    def delete_document(self, *, collection_name: str, doc_id: str) -> None:
        if not self.client.collection_exists(collection_name):
            return
        self.client.delete(
            collection_name=collection_name,
            wait=True,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
        )

    def query(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        limit: int = 5,
    ) -> list[SearchHit]:
        if not self.is_available():
            raise RuntimeError("Qdrant n'est pas configure.")

        response = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )

        points = getattr(response, "points", None)
        if points is None and hasattr(response, "result"):
            points = getattr(response.result, "points", [])
        if points is None:
            points = []

        return [
            SearchHit(
                score=point.score,
                payload=point.payload or {},
                point_id=str(point.id),
            )
            for point in points
        ]

    @staticmethod
    def build_point_id(*, doc_id: str, chunk_index: int) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{chunk_index}"))
