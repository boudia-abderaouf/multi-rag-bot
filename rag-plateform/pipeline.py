import hashlib
import importlib
import json
import logging
from pathlib import Path
from typing import Any, Iterable

import yaml

from config.settings import settings
from ingestion.embedders.openai_embedder import OpenAIEmbedder
from retrieval.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

PROJECT_ROOT = settings.project_root
DOMAINS_DIR = PROJECT_ROOT / "domains"

LOADER_COMPONENTS = {
    "pdf_url": "ingestion.loaders.pdf_url_loader:PdfUrlLoader",
    "pdf_local": "ingestion.loaders.pdf_local_loader:PdfLocalLoader",
    "html_url": "ingestion.loaders.html_loader:HtmlUrlLoader",
}

CHUNKER_COMPONENTS = {
    "article_chunker": "ingestion.chunkers.article_chunker:ArticleChunker",
}


def _resolve_component(path: str):
    module_name, class_name = path.split(":")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def load_documents_config(domain: str) -> list[dict[str, Any]]:
    config_path = DOMAINS_DIR / domain / "documents.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Aucun documents.yaml trouve pour le domaine '{domain}' ({config_path})"
        )

    with config_path.open(encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj) or {}

    return config.get("documents", [])


def iter_chunk_records(chunks_path: Path) -> Iterable[dict[str, Any]]:
    with chunks_path.open(encoding="utf-8") as file_obj:
        for line_number, line in enumerate(file_obj, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Chunk JSONL invalide dans {chunks_path} a la ligne {line_number}"
                ) from exc


def build_chunk_record(
    *,
    doc: dict[str, Any],
    chunk_index: int,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    collection = doc.get("collection") or metadata.get("domaine") or doc["id"]
    chunk_id = hashlib.sha1(
        f"{doc['id']}:{chunk_index}:{text}".encode("utf-8")
    ).hexdigest()
    return {
        "chunk_id": chunk_id,
        "doc_id": doc["id"],
        "document_name": doc["name"],
        "collection": collection,
        "chunk_index": chunk_index,
        "text": text,
        "metadata": metadata,
    }


def write_chunks(
    *,
    domain: str,
    doc: dict[str, Any],
    source_path: Path,
) -> tuple[Path, int]:
    chunker_name = doc.get("chunker")
    component_path = CHUNKER_COMPONENTS.get(chunker_name)
    if component_path is None:
        raise ValueError(f"chunker inconnu '{chunker_name}'")

    chunker_class = _resolve_component(component_path)
    config_path = DOMAINS_DIR / domain / "chunker_config.yaml"
    chunker = chunker_class(config_path=config_path, doc_metadata=doc.get("metadata", {}))

    output_path = settings.chunks_dir / f"{doc['id']}.jsonl"
    total = 0

    with output_path.open("w", encoding="utf-8") as file_obj:
        for chunk in chunker.chunk(source_path):
            record = build_chunk_record(
                doc=doc,
                chunk_index=total,
                text=chunk.text,
                metadata=chunk.metadata,
            )
            file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")
            total += 1

    return output_path, total


def _load_source(doc: dict[str, Any]) -> Path:
    source_type = doc.get("source_type")
    component_path = LOADER_COMPONENTS.get(source_type)
    if component_path is None:
        raise ValueError(f"source_type inconnu '{source_type}'")

    loader_class = _resolve_component(component_path)
    loader = loader_class(doc)
    return loader.load()


def _index_chunks(
    *,
    chunks_path: Path,
    doc: dict[str, Any],
    embedder: OpenAIEmbedder,
    vector_store: QdrantVectorStore,
) -> int:
    collection = doc["collection"]
    vector_store.delete_document(collection_name=collection, doc_id=doc["id"])

    total = 0
    batch: list[dict[str, Any]] = []

    for record in iter_chunk_records(chunks_path):
        batch.append(record)
        if len(batch) >= embedder.batch_size:
            vectors = embedder.embed_texts([r["text"] for r in batch])
            vector_store.upsert_batch(collection_name=collection, records=batch, vectors=vectors)
            total += len(batch)
            batch = []

    if batch:
        vectors = embedder.embed_texts([r["text"] for r in batch])
        vector_store.upsert_batch(collection_name=collection, records=batch, vectors=vectors)
        total += len(batch)

    if total == 0:
        logger.warning(f"[{doc['id']}] Aucun chunk a indexer.")

    return total


def run_ingestion(domain: str) -> None:
    logger.info(f"=== Debut de l'ingestion pour le domaine : {domain} ===")

    documents = load_documents_config(domain)
    if not documents:
        logger.warning(f"Aucun document trouve dans la config du domaine '{domain}'.")
        return

    embedder = OpenAIEmbedder.from_settings(settings)
    vector_store = QdrantVectorStore.from_settings(settings)
    indexing_enabled = embedder.is_available() and vector_store.is_available()

    if not indexing_enabled:
        logger.warning(
            "Indexation vectorielle desactivee : configure OPENAI_API_KEY, "
            "QDRANT_URL et les dependances pour activer embed + store."
        )

    for doc in documents:
        doc_id = doc["id"]

        try:
            source_path = _load_source(doc)
            logger.info(f"[{doc_id}] Source prete : {source_path}")
        except Exception as exc:
            logger.error(f"[{doc_id}] Echec du chargement : {exc}")
            continue

        try:
            chunks_path, total_chunks = write_chunks(domain=domain, doc=doc, source_path=source_path)
            logger.info(f"[{doc_id}] {total_chunks} chunks sauvegardes -> {chunks_path}")
        except Exception as exc:
            logger.error(f"[{doc_id}] Echec du chunking : {exc}")
            continue

        if not indexing_enabled:
            continue

        try:
            indexed = _index_chunks(
                chunks_path=chunks_path,
                doc=doc,
                embedder=embedder,
                vector_store=vector_store,
            )
            logger.info(f"[{doc_id}] {indexed} chunks indexes dans Qdrant.")
        except Exception as exc:
            logger.error(f"[{doc_id}] Echec de l'indexation vectorielle : {exc}")

    logger.info(f"=== Ingestion terminee pour le domaine : {domain} ===")
