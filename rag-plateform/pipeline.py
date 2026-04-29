import logging
from pathlib import Path

import yaml

from ingestion.loaders.pdf_url_loader import PdfUrlLoader

logger = logging.getLogger(__name__)

# Mapping source_type → classe loader
LOADERS = {
    "pdf_url": PdfUrlLoader,
    # "pdf_local": PdfLocalLoader,   # à ajouter plus tard
    # "html":      HtmlLoader,       # à ajouter plus tard
}


def load_documents_config(domain: str) -> list[dict]:
    """Lit le documents.yaml du domaine demandé."""
    config_path = Path(f"domains/{domain}/documents.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Aucun documents.yaml trouvé pour le domaine '{domain}' ({config_path})")

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config.get("documents", [])


def run_ingestion(domain: str) -> None:
    """
    Point d'entrée principal du pipeline d'ingestion.
    Pour l'instant : télécharge et sauvegarde les PDFs du domaine.
    """
    logger.info(f"=== Début de l'ingestion pour le domaine : {domain} ===")

    documents = load_documents_config(domain)
    if not documents:
        logger.warning(f"Aucun document trouvé dans la config du domaine '{domain}'.")
        return

    for doc in documents:
        doc_id = doc["id"]
        source_type = doc.get("source_type")

        loader_class = LOADERS.get(source_type)
        if loader_class is None:
            logger.warning(f"[{doc_id}] source_type inconnu '{source_type}', document ignoré.")
            continue

        try:
            loader = loader_class(doc)
            path = loader.load()
            logger.info(f"[{doc_id}] ✓ Fichier prêt : {path}")
        except Exception as e:
            logger.error(f"[{doc_id}] ✗ Échec du chargement : {e}")

    logger.info(f"=== Ingestion terminée pour le domaine : {domain} ===")