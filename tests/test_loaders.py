import unittest
from pathlib import Path
import shutil

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT / ".tmp-tests"
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from ingestion.loaders.pdf_local_loader import PdfLocalLoader
from ingestion.loaders.pdf_url_loader import PdfUrlLoader


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self._old_data_dir = settings.DATA_DIR
        self._old_force_redownload = settings.FORCE_REDOWNLOAD
        TMP_ROOT.mkdir(exist_ok=True)
        self.temp_dir = TMP_ROOT / self._testMethodName
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        settings.DATA_DIR = self.temp_dir
        settings.FORCE_REDOWNLOAD = False

    def tearDown(self):
        settings.DATA_DIR = self._old_data_dir
        settings.FORCE_REDOWNLOAD = self._old_force_redownload
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pdf_local_loader_returns_resolved_path(self):
        source = self.temp_dir / "sample.pdf"
        source.write_bytes(b"%PDF-1.4 test")

        loader = PdfLocalLoader(
            {
                "id": "sample",
                "name": "Sample PDF",
                "path": str(source),
            }
        )

        self.assertEqual(loader.load(), source.resolve())

    def test_pdf_url_loader_reuses_existing_file(self):
        cached = settings.raw_dir / "sample.pdf"
        cached.write_bytes(b"cached")

        loader = PdfUrlLoader(
            {
                "id": "sample",
                "name": "Sample PDF",
                "url": "https://example.invalid/sample.pdf",
            }
        )

        self.assertEqual(loader.load(), cached)
        self.assertEqual(cached.read_bytes(), b"cached")
