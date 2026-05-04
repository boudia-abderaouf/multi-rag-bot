import logging
from html.parser import HTMLParser
from pathlib import Path

import httpx

from config.settings import settings
from ingestion.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class _HtmlToTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "br", "li", "section", "article", "div", "h1", "h2", "h3", "h4"}:
            self._chunks.append("\n")

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self._chunks.append(data.strip())

    def get_text(self) -> str:
        text = " ".join(self._chunks)
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())


class HtmlUrlLoader(BaseLoader):
    """
    Telecharge une page HTML et en sauvegarde le texte nettoye localement.
    """

    def __init__(self, doc_config: dict):
        super().__init__(doc_config)
        self.url = doc_config["url"]
        self.dest: Path = settings.raw_dir / f"{self.doc_id}.txt"

    def load(self) -> Path:
        if self.dest.exists() and not settings.FORCE_REDOWNLOAD:
            logger.info(f"[{self.doc_id}] HTML deja present, re-utilisation : {self.dest}")
            return self.dest

        response = httpx.get(
            self.url,
            follow_redirects=True,
            timeout=settings.DOWNLOAD_TIMEOUT,
        )
        response.raise_for_status()

        parser = _HtmlToTextParser()
        parser.feed(response.text)
        self.dest.write_text(parser.get_text(), encoding="utf-8")
        logger.info(f"[{self.doc_id}] Texte HTML sauvegarde -> {self.dest}")
        return self.dest
