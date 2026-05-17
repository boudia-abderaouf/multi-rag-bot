import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))

from ingestion.chunkers.article_chunker import ArticleChunker, format_article_id


class GenericArticleChunkerTest(unittest.TestCase):
    def test_generic_art_boundary(self):
        chunker = self._chunker("chunker_generic.yaml")
        line = "Art. 12.-Le contrat est conclu pour une durée déterminée."
        self.assertEqual(chunker._parse_article_boundary(line), "Art. 12")

    def test_generic_does_not_match_random_line(self):
        chunker = self._chunker("chunker_generic.yaml")
        self.assertIsNone(chunker._parse_article_boundary("Chapitre I : Dispositions générales"))

    def test_generic_no_preamble_rules(self):
        chunker = self._chunker("chunker_generic.yaml")
        raw = "Art. 12.-Corps de l'article sans en-tête Legifrance."
        self.assertEqual(chunker._strip_preamble(raw), raw)

    def test_generic_prepare_text(self):
        chunker = self._chunker("chunker_generic.yaml")
        out = chunker._prepare_article_text("Art. 12", "Art. 12.-Corps juridique ici.")
        self.assertTrue(out.startswith("Art. 12.- "))
        self.assertIn("Corps juridique", out)

    def _chunker(self, fixture_name: str) -> ArticleChunker:
        config = PROJECT_ROOT / "tests" / "fixtures" / fixture_name
        return ArticleChunker(config_path=config, doc_metadata={"domaine": "test"})


class CesedaArticleChunkerTest(unittest.TestCase):
    def test_format_article_id(self):
        self.assertEqual(
            format_article_id("Art. {type}. {number}", article_type="l", number="512-1"),
            "Art. L. 512-1",
        )

    def test_parse_art_format(self):
        chunker = self._ceseda_chunker()
        line = 'Art. L. 142-1.-Afin de mieux garantir le droit au séjour.'
        self.assertEqual(chunker._parse_article_boundary(line), "Art. L. 142-1")

    def test_parse_legifrance_format(self):
        chunker = self._ceseda_chunker()
        line = (
            "L. 512-1 Ordonnance n°2020-1733 du 16 décembre 2020 - art. - "
            "Conseil Constit. Juricaf Le bénéfice de la protection subsidiaire"
        )
        self.assertEqual(chunker._parse_article_boundary(line), "Art. L. 512-1")

    def test_does_not_match_livre(self):
        chunker = self._ceseda_chunker()
        self.assertIsNone(chunker._parse_article_boundary("Livre IV : SÉJOUR EN FRANCE"))

    def test_strip_preamble_ordonnance(self):
        chunker = self._ceseda_chunker()
        raw = (
            "L. 512-1 Ordonnance n°2020-1733 du 16 décembre 2020 - art. - "
            "Juricaf Le bénéfice de la protection subsidiaire est accordé."
        )
        body = chunker._strip_preamble(raw)
        self.assertTrue(body.startswith("Le bénéfice"))

    def test_clean_page_marker(self):
        chunker = self._ceseda_chunker()
        text = "Texte utile p.198 Code de l'entrée et du séjour des étrangers suite."
        cleaned = chunker._clean_text(text)
        self.assertNotIn("p.198", cleaned)
        self.assertIn("Texte utile", cleaned)

    def test_emit_one_article_per_id(self):
        chunker = self._ceseda_chunker()
        c1 = list(
            chunker._emit(
                "Art. L. 512-1",
                ["L. 512-1 Ordonnance n°2020 Juricaf Premier article sur la protection subsidiaire."],
                {},
            )
        )
        c2 = list(
            chunker._emit(
                "Art. L. 512-2",
                ["L. 512-2 Ordonnance n°2020 Juricaf Deuxième article sur les exclusions."],
                {},
            )
        )
        self.assertEqual(c1[0].metadata["article_id"], "Art. L. 512-1")
        self.assertNotIn("512-2", c1[0].text)

    def test_custom_domain_config_from_temp_file(self):
        """Un autre domaine peut définir ses propres règles sans toucher au code."""
        yaml_content = """
article_boundary_pattern: "^Section\\\\s+(\\\\d+)\\\\s*[-:]\\\\s*"
article_id:
  mode: template
  template: "Section {number}"
prefix_article_id: false
min_chunk_size: 5
chunk_size: 800
chunk_overlap: 0
"""
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
            tmp.write(yaml_content)
            tmp_path = Path(tmp.name)

        chunker = ArticleChunker(config_path=tmp_path, doc_metadata={})
        self.assertEqual(chunker._parse_article_boundary("Section 4 - Obligations"), "Section 4")
        tmp_path.unlink()

    def _ceseda_chunker(self) -> ArticleChunker:
        config = PROJECT_ROOT / "domains" / "droit_etranger" / "chunker_config.yaml"
        return ArticleChunker(config_path=config, doc_metadata={"domaine": "droit_etranger"})


if __name__ == "__main__":
    unittest.main()
