import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))
sys.path.insert(0, str(PROJECT_ROOT))

import retrieval.retriever as retriever_module
from retrieval.retriever import Retriever
from retrieval.vector_store import QdrantVectorStore, SearchHit


class RetrievalTests(unittest.TestCase):
    def test_resolve_collection_names_uses_documents_config(self):
        original_loader = retriever_module.load_documents_config
        retriever_module.load_documents_config = lambda domain: [
            {"collection": "collection_a"},
            {"collection": "collection_b"},
            {"collection": "collection_a"},
        ]

        try:
            collections = Retriever.resolve_collection_names("droit_etranger")
        finally:
            retriever_module.load_documents_config = original_loader

        self.assertEqual(collections, ["collection_a", "collection_b"])

    def test_point_id_is_deterministic(self):
        first = QdrantVectorStore.build_point_id(doc_id="demo", chunk_index=1)
        second = QdrantVectorStore.build_point_id(doc_id="demo", chunk_index=1)
        third = QdrantVectorStore.build_point_id(doc_id="demo", chunk_index=2)

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_build_prompt_formats_hits_into_context(self):
        retriever = Retriever(embedder=object(), vector_store=object())
        hits = [
            SearchHit(
                score=0.9,
                point_id="1",
                payload={
                    "text": "Contenu A",
                    "metadata": {"article_id": "Art. L111-1"},
                },
            ),
            SearchHit(
                score=0.8,
                point_id="2",
                payload={
                    "text": "Contenu B",
                    "metadata": {"article_id": "Art. L111-2"},
                },
            ),
        ]

        prompt = retriever.build_prompt(
            domain="droit_etranger",
            question="Quel article parle du sejour ?",
            hits=hits,
        )

        self.assertIn("Art. L111-1", prompt)
        self.assertIn("Contenu B", prompt)
        self.assertIn("Quel article parle du sejour ?", prompt)
