import logging
from pathlib import Path

from config.settings import settings
from ingestion.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class PdfLocalLoader(BaseLoader):
    """
    Retourne le chemin d'un PDF deja present localement.
    """

    def __init__(self, doc_config: dict):
        super().__init__(doc_config)
        self.path = Path(doc_config["path"]).expanduser()

    def load(self) -> Path:
        resolved = self.path if self.path.is_absolute() else (settings.project_root / self.path)
        resolved = resolved.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"[{self.doc_id}] PDF local introuvable : {resolved}")
        if resolved.suffix.lower() != ".pdf":
            logger.warning(f"[{self.doc_id}] Le fichier local n'a pas l'extension .pdf : {resolved}")
        logger.info(f"[{self.doc_id}] PDF local pret : {resolved}")
        return resolved
