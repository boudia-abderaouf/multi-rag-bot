import json
import unittest
from pathlib import Path
import shutil

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp-tests"
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from ingestion.chunkers.base import Chunk
import pipeline


class FakeLoader:
    def __init__(self, doc_config):
        self.doc_config = doc_config

    def load(self):
        path = settings.raw_dir / f"{self.doc_config['id']}.pdf"
        path.write_bytes(b"%PDF-1.4 fake")
        return path


class FakeChunker:
    def __init__(self, config_path, doc_metadata):
        self.doc_metadata = doc_metadata

    def chunk(self, pdf_path):
        yield Chunk(
            text="Article L111-1 contenu alpha",
            metadata={"article_id": "Art. L111-1", **self.doc_metadata},
        )
        yield Chunk(
            text="Article L111-2 contenu beta",
            metadata={"article_id": "Art. L111-2", **self.doc_metadata},
        )


class FakeEmbedder:
    batch_size = 32

    def __init__(self):
        self.calls = []

    @classmethod
    def from_settings(cls, _settings):
        return cls()

    def is_available(self):
        return True

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[float(index + 1), float(len(text))] for index, text in enumerate(texts)]


class FakeVectorStore:
    instances = []

    def __init__(self):
        self.calls = []
        type(self).instances.append(self)

    @classmethod
    def from_settings(cls, _settings):
        return cls()

    def is_available(self):
        return True

    def delete_document(self, *, collection_name, doc_id):
        self.calls.append(
            {
                "method": "delete_document",
                "collection_name": collection_name,
                "doc_id": doc_id,
            }
        )

    def upsert_batch(self, *, collection_name, records, vectors):
        self.calls.append(
            {
                "method": "upsert_batch",
                "collection_name": collection_name,
                "records": records,
                "vectors": vectors,
            }
        )


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self._old_data_dir = settings.DATA_DIR
        TMP_ROOT.mkdir(exist_ok=True)
        self.temp_dir = TMP_ROOT / self._testMethodName
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        settings.DATA_DIR = self.temp_dir

        self._old_loader_components = pipeline.LOADER_COMPONENTS
        self._old_chunker_components = pipeline.CHUNKER_COMPONENTS
        self._old_resolve_component = pipeline._resolve_component
        self._old_load_documents_config = pipeline.load_documents_config
        self._old_embedder_cls = pipeline.OpenAIEmbedder
        self._old_vector_store_cls = pipeline.QdrantVectorStore

        pipeline.LOADER_COMPONENTS = {"fake_loader": "fake_loader"}
        pipeline.CHUNKER_COMPONENTS = {"fake_chunker": "fake_chunker"}
        pipeline._resolve_component = lambda key: {
            "fake_loader": FakeLoader,
            "fake_chunker": FakeChunker,
        }[key]
        pipeline.load_documents_config = lambda domain: [
            {
                "id": "doc_demo",
                "name": "Document demo",
                "source_type": "fake_loader",
                "chunker": "fake_chunker",
                "collection": "demo_collection",
                "metadata": {"domaine": domain, "langue": "fr"},
            }
        ]
        pipeline.OpenAIEmbedder = FakeEmbedder
        pipeline.QdrantVectorStore = FakeVectorStore
        FakeVectorStore.instances.clear()

    def tearDown(self):
        settings.DATA_DIR = self._old_data_dir
        pipeline.LOADER_COMPONENTS = self._old_loader_components
        pipeline.CHUNKER_COMPONENTS = self._old_chunker_components
        pipeline._resolve_component = self._old_resolve_component
        pipeline.load_documents_config = self._old_load_documents_config
        pipeline.OpenAIEmbedder = self._old_embedder_cls
        pipeline.QdrantVectorStore = self._old_vector_store_cls
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_run_ingestion_writes_chunk_jsonl_and_indexes_records(self):
        pipeline.run_ingestion("droit_etranger")

        chunks_path = settings.chunks_dir / "doc_demo.jsonl"
        self.assertTrue(chunks_path.exists())

        records = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["doc_id"], "doc_demo")
        self.assertEqual(records[0]["collection"], "demo_collection")
        self.assertEqual(records[0]["metadata"]["domaine"], "droit_etranger")
        self.assertEqual(records[0]["chunk_index"], 0)

        self.assertEqual(len(FakeVectorStore.instances), 1)
        store = FakeVectorStore.instances[0]
        self.assertEqual(len(store.calls), 2)
        self.assertEqual(store.calls[0]["method"], "delete_document")
        self.assertEqual(store.calls[0]["doc_id"], "doc_demo")
        self.assertEqual(store.calls[1]["method"], "upsert_batch")
        self.assertEqual(store.calls[1]["collection_name"], "demo_collection")
        self.assertEqual(len(store.calls[1]["vectors"]), 2)
