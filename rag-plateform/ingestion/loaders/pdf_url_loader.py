import hashlib
import logging
from pathlib import Path

import httpx

from config.settings import settings
from ingestion.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class PdfUrlLoader(BaseLoader):
    """
    Télécharge un PDF depuis une URL et le sauvegarde dans data/raw/.
    Identique en local et en prod — seul DATA_DIR change via .env.
    """

    def __init__(self, doc_config: dict):
        super().__init__(doc_config)
        self.url = doc_config["url"]
        self.dest: Path = settings.raw_dir / f"{self.doc_id}.pdf"

    def load(self) -> Path:
        logger.info(f"[{self.doc_id}] Téléchargement depuis : {self.url}")

        try:
            response = httpx.get(
                self.url,
                follow_redirects=True,
                timeout=settings.DOWNLOAD_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"[{self.doc_id}] Erreur HTTP {e.response.status_code} : {self.url}")
            raise
        except httpx.RequestError as e:
            logger.error(f"[{self.doc_id}] Erreur réseau : {e}")
            raise

        content = response.content
        self.dest.write_bytes(content)

        sha256 = hashlib.sha256(content).hexdigest()
        logger.info(f"[{self.doc_id}] Sauvegardé → {self.dest} ({len(content) / 1024:.1f} Ko, sha256={sha256[:12]}...)")

        return self.dest