import logging
import re
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
            (item.get("level", index + 1), item["label"], re.compile(item["pattern"]))
            for index, item in enumerate(config.get("hierarchy", []))
        ]
        self.hierarchy_levels = {
            label: level for level, label, _pattern in self.hierarchy_patterns
        }
        self.chunk_size = config.get("chunk_size", 800)
        self.chunk_overlap = config.get("chunk_overlap", 100)
        self.min_chunk_size = config.get("min_chunk_size", 50)
        self.doc_metadata = doc_metadata

    def chunk(self, pdf_path: Path):
        """
        Lit le PDF page par page et yield les chunks au fur et a mesure.
        Ne charge jamais plus d'une page en memoire a la fois.
        """
        doc = fitz.open(pdf_path)
        hierarchy_state: dict[str, str] = {}
        current_article_id = None
        current_lines: list[str] = []

        for page in doc:
            for line in page.get_text().splitlines():
                line = line.strip().lstrip('"').strip()
                if not line:
                    continue

                for level, label, pattern in self.hierarchy_patterns:
                    if pattern.match(line):
                        hierarchy_state[label] = line
                        for known_label, known_level in self.hierarchy_levels.items():
                            if known_level > level:
                                hierarchy_state.pop(known_label, None)
                        break

                match = self.article_re.match(line)
                if match:
                    if current_article_id and current_lines:
                        yield from self._emit(current_article_id, current_lines, hierarchy_state)
                    current_article_id = match.group(1)
                    current_lines = [line]
                elif current_article_id:
                    current_lines.append(line)

        if current_article_id and current_lines:
            yield from self._emit(current_article_id, current_lines, hierarchy_state)

        doc.close()
        logger.info(f"Chunking termine : {pdf_path.name}")

    def _emit(self, article_id: str, lines: list[str], hierarchy: dict[str, str]):
        text = " ".join(lines)
        if len(text) < self.min_chunk_size:
            return

        article_type_match = re.search(r"\b([LRD])\.?\s*\d", article_id)
        metadata = {
            "article_id": article_id,
            "article_type": article_type_match.group(1) if article_type_match else "",
            **{label.lower(): value for label, value in hierarchy.items()},
            **self.doc_metadata,
        }

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
