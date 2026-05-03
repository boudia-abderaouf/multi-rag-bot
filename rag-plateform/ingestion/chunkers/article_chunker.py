import re
import logging
from pathlib import Path

import fitz  # PyMuPDF
import yaml

from ingestion.chunkers.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)


class ArticleChunker(BaseChunker):

    def __init__(self, config_path: Path, doc_metadata: dict):
        with config_path.open(encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.article_re = re.compile(config["article_pattern"])
        self.hierarchy_patterns = [
            (h["label"], re.compile(h["pattern"]))
            for h in config.get("hierarchy", [])
        ]
        self.chunk_size = config.get("chunk_size", 800)
        self.chunk_overlap = config.get("chunk_overlap", 100)
        self.min_chunk_size = config.get("min_chunk_size", 50)
        self.doc_metadata = doc_metadata

    def chunk(self, pdf_path: Path):
        """
        Lit le PDF page par page et yield les chunks au fur et à mesure.
        Ne charge jamais plus d'une page en mémoire à la fois.
        """
        doc = fitz.open(pdf_path)
        hierarchy_state = {}
        current_article_id = None
        current_lines = []

        for page_num, page in enumerate(doc, start=1):
            for line in page.get_text().splitlines():
                line = line.strip()
                if not line:
                    continue

                # Mise à jour du curseur hiérarchique
                for label, pattern in self.hierarchy_patterns:
                    if pattern.match(line):
                        hierarchy_state[label] = line
                        break

                # Début d'un nouvel article
                match = self.article_re.match(line)
                if match:
                    if current_article_id and current_lines:
                        yield from self._emit(current_article_id, current_lines, hierarchy_state)
                    current_article_id = match.group(1)
                    current_lines = [line]
                elif current_article_id:
                    current_lines.append(line)

        # Dernier article
        if current_article_id and current_lines:
            yield from self._emit(current_article_id, current_lines, hierarchy_state)

        doc.close()
        logger.info(f"Chunking terminé : {pdf_path.name}")

    def _emit(self, article_id: str, lines: list[str], hierarchy: dict):
        text = " ".join(lines)
        if len(text) < self.min_chunk_size:
            return

        metadata = {
            "article_id": article_id,
            "article_type": article_id[0] if article_id else "",
            **{label.lower(): value for label, value in hierarchy.items()},
            **self.doc_metadata,
        }

        # Découpe en sous-chunks si l'article dépasse chunk_size (en mots)
        max_words = int(self.chunk_size / 1.3)
        overlap_words = int(self.chunk_overlap / 1.3)
        words = text.split()

        if len(words) <= max_words:
            yield Chunk(text=text, metadata=metadata)
            return

        start = 0
        while start < len(words):
            end = min(start + max_words, len(words))
            yield Chunk(text=" ".join(words[start:end]), metadata=metadata)
            if end == len(words):
                break
            start = end - overlap_words
