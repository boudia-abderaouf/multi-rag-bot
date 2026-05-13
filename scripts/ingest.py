"""
Script d'ingestion a lancer manuellement ou via un job planifie.

Usage :
    python scripts/ingest.py --domain droit_etranger
"""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))

from pipeline import run_ingestion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    parser = argparse.ArgumentParser(description="Lance le pipeline d'ingestion pour un domaine.")
    parser.add_argument(
        "--domain",
        required=True,
        help="Nom du domaine a ingerer (ex: droit_etranger)",
    )
    args = parser.parse_args()
    run_ingestion(domain=args.domain)


if __name__ == "__main__":
    main()
