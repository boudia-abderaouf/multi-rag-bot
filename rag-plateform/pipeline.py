import json
import logging
from pathlib import Path

import yaml

from config.settings import settings
from ingestion.loaders.pdf_url_loader import PdfUrlLoader
from ingestion.chunkers.article_chunker import ArticleChunker

logger = logging.getLogger(__name__)

LOADERS = {
    "pdf_url": PdfUrlLoader,
}

CHUNKERS = {
    "article_chunker": ArticleChunker,
}


def load_documents_config(domain: str) -> list[dict]:
    config_path = Path(f"domains/{domain}/documents.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Aucun documents.yaml trouvé pour le domaine '{domain}' ({config_path})")

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config.get("documents", [])


def run_ingestion(domain: str) -> None:
    logger.info(f"=== Début de l'ingestion pour le domaine : {domain} ===")

    documents = load_documents_config(domain)
    if not documents:
        logger.warning(f"Aucun document trouvé dans la config du domaine '{domain}'.")
        return

    for doc in documents:
        doc_id = doc["id"]
        source_type = doc.get("source_type")
        chunker_name = doc.get("chunker")

        # --- Étape 1 : Load ---
        loader_class = LOADERS.get(source_type)
        if loader_class is None:
            logger.warning(f"[{doc_id}] source_type inconnu '{source_type}', document ignoré.")
            continue

        try:
            loader = loader_class(doc)
            pdf_path = loader.load()
            logger.info(f"[{doc_id}] ✓ PDF prêt : {pdf_path}")
        except Exception as e:
            logger.error(f"[{doc_id}] ✗ Échec du chargement : {e}")
            continue

        # --- Étape 2 : Chunk ---
        chunker_class = CHUNKERS.get(chunker_name)
        if chunker_class is None:
            logger.warning(f"[{doc_id}] chunker inconnu '{chunker_name}', chunking ignoré.")
            continue

        config_path = Path(f"domains/{domain}/chunker_config.yaml")
        chunker = chunker_class(config_path=config_path, doc_metadata=doc.get("metadata", {}))

        output_path = settings.chunks_dir / f"{doc_id}.jsonl"
        total = 0

        try:
            with output_path.open("w", encoding="utf-8") as f:
                for chunk in chunker.chunk(pdf_path):
                    f.write(json.dumps({"text": chunk.text, "metadata": chunk.metadata}, ensure_ascii=False) + "\n")
                    total += 1
            logger.info(f"[{doc_id}] ✓ {total} chunks sauvegardés → {output_path}")
        except Exception as e:
            logger.error(f"[{doc_id}] ✗ Échec du chunking : {e}")

    logger.info(f"=== Ingestion terminée pour le domaine : {domain} ===")
