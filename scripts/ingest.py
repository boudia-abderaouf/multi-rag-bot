"""
Script d'ingestion a lancer manuellement ou via un job planifie.

Usage :
    python scripts/ingest.py --domain droit_etranger
"""

import argparse
import logging
from project_bootstrap import configure_project_path

configure_project_path()

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
