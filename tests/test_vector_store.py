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
    def __init__(self, *, fail_first_delete: bool = False):
        self.fail_first_delete = fail_first_delete
        self.collection_exists_calls = []
        self.create_payload_index_calls = []
        self.delete_calls = []

    def collection_exists(self, collection_name):
        self.collection_exists_calls.append(collection_name)
        return True

    def create_payload_index(self, **kwargs):
        self.create_payload_index_calls.append(kwargs)

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)
        if self.fail_first_delete and len(self.delete_calls) == 1:
            raise RuntimeError('Index required but not found for "doc_id"')


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

    def test_delete_document_ensures_doc_id_index(self):
        client = FakeClient()
        store = QdrantVectorStore(url="https://example.qdrant.io", client=client)

        store.delete_document(collection_name="droit_etranger", doc_id="ceseda")

        self.assertEqual(len(client.create_payload_index_calls), 1)
        self.assertEqual(client.create_payload_index_calls[0]["field_name"], "doc_id")
        self.assertEqual(client.create_payload_index_calls[0]["field_schema"], "keyword")
        self.assertEqual(len(client.delete_calls), 1)

    def test_delete_document_retries_when_doc_id_index_is_missing(self):
        client = FakeClient(fail_first_delete=True)
        store = QdrantVectorStore(url="https://example.qdrant.io", client=client)

        store.delete_document(collection_name="droit_etranger", doc_id="ceseda")

        self.assertEqual(len(client.create_payload_index_calls), 2)
        self.assertEqual(len(client.delete_calls), 2)

