import logging
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import yaml

from ingestion.chunkers.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)

# Défaut générique : "Art. 12.-Texte" ou "Article 3 : texte"
_DEFAULT_ARTICLE_BOUNDARY = (
    r'^"?\s*'
    r"(Art(?:icle)?\.\s+.+?)"
    r"(?:\.-\s*|\s+|:\s+)"
)

_WHITESPACE_RE = re.compile(r"\s+")


def format_article_id(template: str, *, article_type: str, number: str) -> str:
    return template.format(type=article_type.upper(), number=number)


class ArticleChunker(BaseChunker):
    """
    Chunker par article, entièrement piloté par chunker_config.yaml du domaine.

    Clés de configuration (toutes optionnelles sauf les tailles) :
      article_boundary_pattern — regex de début d'article (match en début de ligne)
      article_id — mode de construction de l'identifiant (template | group)
      text_cleanup — liste de regex à supprimer dans le texte
      preamble — règles de retrait d'en-tête avant le corps de l'article
      territory_markers — détection de variantes territoriales (métadonnée)
      prefix_article_id — préfixer le chunk avec "{article_id}.- "
      hierarchy, chunk_size, chunk_overlap, min_chunk_size
    """

    def __init__(self, config_path: Path, doc_metadata: dict):
        with config_path.open(encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        boundary = config.get("article_boundary_pattern") or config.get("article_pattern")
        if not boundary:
            boundary = _DEFAULT_ARTICLE_BOUNDARY
        self.article_boundary_re = re.compile(boundary, re.IGNORECASE)

        article_id_cfg = config.get("article_id") or {}
        self.article_id_mode = article_id_cfg.get("mode", "auto")
        self.article_id_template = article_id_cfg.get(
            "template", "Art. {type}. {number}"
        )
        self.article_id_group = int(article_id_cfg.get("group", 1))

        self.text_cleanup_res = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in config.get("text_cleanup", [])
        ]
        self.preamble_rules = self._load_preamble_rules(config.get("preamble", []))
        self.territory_markers = [
            (re.compile(item["pattern"], re.IGNORECASE), item["label"])
            for item in config.get("territory_markers", [])
        ]
        self.prefix_article_id = config.get("prefix_article_id", True)
        self.territory_sample_chars = int(config.get("territory_sample_chars", 500))

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
        self._articles_seen = 0
        self._chunks_emitted = 0

    @staticmethod
    def _load_preamble_rules(raw_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        for item in raw_rules:
            rule = {"re": re.compile(item["pattern"], re.IGNORECASE | re.DOTALL)}
            if "keep_group" in item:
                rule["keep_group"] = int(item["keep_group"])
            if item.get("strip_match"):
                rule["strip_match"] = True
            rules.append(rule)
        return rules

    def chunk(self, pdf_path: Path):
        """Lit le PDF page par page et yield les chunks au fur et à mesure."""
        doc = fitz.open(pdf_path)
        hierarchy_state: dict[str, str] = {}
        current_article_id: str | None = None
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

                boundary = self._parse_article_boundary(line)
                if boundary:
                    if current_article_id and current_lines:
                        yield from self._emit(
                            current_article_id, current_lines, hierarchy_state
                        )
                    current_article_id = boundary
                    current_lines = [line]
                elif current_article_id:
                    current_lines.append(line)

        if current_article_id and current_lines:
            yield from self._emit(current_article_id, current_lines, hierarchy_state)

        doc.close()
        logger.info(
            f"Chunking termine : {pdf_path.name} — "
            f"{self._articles_seen} articles, {self._chunks_emitted} chunks"
        )

    def _parse_article_boundary(self, line: str) -> str | None:
        match = self.article_boundary_re.match(line)
        if not match:
            return None

        if self.article_id_mode == "group":
            return match.group(self.article_id_group).strip()

        if self.article_id_mode in ("template", "auto") and match.lastindex and match.lastindex >= 2:
            return format_article_id(
                self.article_id_template,
                article_type=match.group(1),
                number=match.group(2),
            )

        if self.article_id_mode == "template" and match.lastindex and match.lastindex >= 1:
            return self.article_id_template.format(
                type=match.group(1),
                number=match.group(1),
            )

        # mode "auto" : 1 groupe → identifiant brut

        raw = match.group(1).strip()
        parsed = re.match(
            r"^(?:Art(?:icle)?\.\s*)?([LRD])\.\s*(\d{3,4}-\d{1,3}(?:-\d{1,3})?)$",
            raw,
            re.IGNORECASE,
        )
        if parsed:
            return format_article_id(
                self.article_id_template,
                article_type=parsed.group(1),
                number=parsed.group(2),
            )
        return raw

    def _emit(self, article_id: str, lines: list[str], hierarchy: dict[str, str]):
        raw_text = " ".join(lines)
        text = self._prepare_article_text(article_id, raw_text)
        if len(text) < self.min_chunk_size:
            return

        self._articles_seen += 1
        article_type_match = re.search(r"\b([LRD])\.\s*\d", article_id)
        metadata = {
            "article_id": article_id,
            "article_type": article_type_match.group(1) if article_type_match else "",
            **{label.lower(): value for label, value in hierarchy.items()},
            **self.doc_metadata,
        }
        territoire = self._detect_territoire(text)
        if territoire:
            metadata["territoire"] = territoire

        max_words = int(self.chunk_size / 1.3)
        overlap_words = int(self.chunk_overlap / 1.3)
        words = text.split()

        if len(words) <= max_words:
            self._chunks_emitted += 1
            yield Chunk(text=text, metadata=metadata)
            return

        start = 0
        while start < len(words):
            end = min(start + max_words, len(words))
            self._chunks_emitted += 1
            yield Chunk(text=" ".join(words[start:end]), metadata=metadata)
            if end == len(words):
                break
            start = end - overlap_words

    def _prepare_article_text(self, article_id: str, raw_text: str) -> str:
        body = self._strip_preamble(raw_text)
        body = self._clean_text(body)
        if not body:
            body = self._clean_text(raw_text)
        if not body:
            return ""
        if self.prefix_article_id:
            return f"{article_id}.- {body}"
        return body

    def _clean_text(self, text: str) -> str:
        for pattern in self.text_cleanup_res:
            text = pattern.sub(" ", text)
        return _WHITESPACE_RE.sub(" ", text).strip()

    def _strip_preamble(self, text: str) -> str:
        text = text.strip()
        for rule in self.preamble_rules:
            match = rule["re"].match(text)
            if not match:
                continue
            if "keep_group" in rule:
                return match.group(rule["keep_group"]).strip()
            if rule.get("strip_match"):
                text = text[match.end() :].strip()
        return text

    def _detect_territoire(self, text: str) -> str | None:
        sample = text[: self.territory_sample_chars]
        for pattern, label in self.territory_markers:
            if pattern.search(sample):
                return label
        return None
