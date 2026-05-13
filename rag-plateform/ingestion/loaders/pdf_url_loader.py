import hashlib
import logging
from pathlib import Path

import httpx

from config.settings import settings
from ingestion.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class PdfUrlLoader(BaseLoader):
    """
    Telecharge un PDF depuis une URL et le sauvegarde dans data/raw/.
    Identique en local et en prod : seul DATA_DIR change via .env.
    """

    def __init__(self, doc_config: dict):
        super().__init__(doc_config)
        self.url = doc_config["url"]
        self.dest: Path = settings.raw_dir / f"{self.doc_id}.pdf"

    def load(self) -> Path:
        if self.dest.exists() and not settings.FORCE_REDOWNLOAD:
            logger.info(f"[{self.doc_id}] PDF deja present, re-utilisation : {self.dest}")
            return self.dest

        logger.info(f"[{self.doc_id}] Telechargement depuis : {self.url}")

        try:
            response = httpx.get(
                self.url,
                follow_redirects=True,
                timeout=settings.DOWNLOAD_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(f"[{self.doc_id}] Erreur HTTP {exc.response.status_code} : {self.url}")
            raise
        except httpx.RequestError as exc:
            logger.error(f"[{self.doc_id}] Erreur reseau : {exc}")
            raise

        content = response.content
        self.dest.write_bytes(content)

        sha256 = hashlib.sha256(content).hexdigest()
        logger.info(
            f"[{self.doc_id}] Sauvegarde -> {self.dest} "
            f"({len(content) / 1024:.1f} Ko, sha256={sha256[:12]}...)"
        )

        return self.dest
