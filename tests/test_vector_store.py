import types
import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))
sys.path.insert(0, str(PROJECT_ROOT))

import retrieval.vector_store as vector_store_module
from retrieval.vector_store import QdrantVectorStore


class FakeClient:
    def __init__(self, *, fail_first_delete: bool = False, collection_exists: bool = False):
        self.fail_first_delete = fail_first_delete
        self.collection_exists_value = collection_exists
        self.collection_exists_calls = []
        self.create_collection_calls = []
        self.create_payload_index_calls = []
        self.delete_calls = []
        self.upsert_calls = []

    def collection_exists(self, collection_name):
        self.collection_exists_calls.append(collection_name)
        return self.collection_exists_value

    def create_collection(self, **kwargs):
        self.create_collection_calls.append(kwargs)
        self.collection_exists_value = True

    def create_payload_index(self, **kwargs):
        self.create_payload_index_calls.append(kwargs)

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)
        if self.fail_first_delete and len(self.delete_calls) == 1:
            raise RuntimeError('Index required but not found for "doc_id"')

    def upsert(self, **kwargs):
        self.upsert_calls.append(kwargs)


class VectorStoreTests(unittest.TestCase):
    def setUp(self):
        self._old_models = vector_store_module.models
        vector_store_module.models = types.SimpleNamespace(
            PayloadSchemaType=types.SimpleNamespace(KEYWORD="keyword"),
            FilterSelector=lambda **kwargs: kwargs,
            Filter=lambda **kwargs: kwargs,
            FieldCondition=lambda **kwargs: kwargs,
            MatchValue=lambda **kwargs: kwargs,
        )

    def tearDown(self):
        vector_store_module.models = self._old_models

    def _sample_records(self, count: int = 2):
        return [
            {
                "doc_id": "ceseda",
                "chunk_id": f"chunk-{index}",
                "chunk_index": index,
                "document_name": "CESEDA",
                "collection": "droit_etranger",
                "text": f"Texte juridique {index}",
                "metadata": {"article_id": f"Art. L. {index}-1"},
            }
            for index in range(count)
        ]

    def test_upsert_batch_sends_points(self):
        client = FakeClient(collection_exists=True)
        vector_store_module.models.PointStruct = (
            lambda *, id, vector, payload: {"id": id, "vector": vector, "payload": payload}
        )
        vector_store_module.models.VectorParams = lambda **kwargs: kwargs
        vector_store_module.models.Distance = types.SimpleNamespace(COSINE="cosine")
        store = QdrantVectorStore(url="https://example.qdrant.io", client=client)
        records = self._sample_records()
        vectors = [[0.1, 0.2], [0.3, 0.4]]

        store.upsert_batch(
            collection_name="droit_etranger",
            records=records,
            vectors=vectors,
        )

        self.assertEqual(len(client.upsert_calls), 1)
        points = client.upsert_calls[0]["points"]
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["payload"]["doc_id"], "ceseda")

    def test_replace_document_batches_upserts(self):
        client = FakeClient(collection_exists=True)
        vector_store_module.models.PointStruct = (
            lambda *, id, vector, payload: {"id": id, "vector": vector, "payload": payload}
        )
        vector_store_module.models.VectorParams = lambda **kwargs: kwargs
        vector_store_module.models.Distance = types.SimpleNamespace(COSINE="cosine")
        store = QdrantVectorStore(url="https://example.qdrant.io", client=client)
        records = self._sample_records(count=3)
        vectors = [[0.1], [0.2], [0.3]]

        store.replace_document(
            collection_name="droit_etranger",
            doc_id="ceseda",
            records=records,
            vectors=vectors,
            batch_size=2,
        )

        self.assertEqual(len(client.delete_calls), 1)
        self.assertEqual(len(client.upsert_calls), 2)
        self.assertEqual(len(client.upsert_calls[0]["points"]), 2)
        self.assertEqual(len(client.upsert_calls[1]["points"]), 1)

    def test_delete_document_ensures_doc_id_index(self):
        client = FakeClient(collection_exists=True)
        store = QdrantVectorStore(url="https://example.qdrant.io", client=client)

        store.delete_document(collection_name="droit_etranger", doc_id="ceseda")

        self.assertEqual(len(client.create_payload_index_calls), 1)
        self.assertEqual(client.create_payload_index_calls[0]["field_name"], "doc_id")
        self.assertEqual(client.create_payload_index_calls[0]["field_schema"], "keyword")
        self.assertEqual(len(client.delete_calls), 1)

    def test_delete_document_retries_when_doc_id_index_is_missing(self):
        client = FakeClient(fail_first_delete=True, collection_exists=True)
        store = QdrantVectorStore(url="https://example.qdrant.io", client=client)

        store.delete_document(collection_name="droit_etranger", doc_id="ceseda")

        self.assertEqual(len(client.create_payload_index_calls), 2)
        self.assertEqual(len(client.delete_calls), 2)

