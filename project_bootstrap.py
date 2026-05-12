from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
RAG_PLATFORM_ROOT = PROJECT_ROOT / "rag-plateform"


def configure_project_path() -> None:
    for path in (PROJECT_ROOT, RAG_PLATFORM_ROOT):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
