import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "rag-plateform"))

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
        help="Nom du domaine à ingérer (ex: droit_etranger)",
    )
    args = parser.parse_args()
    run_ingestion(domain=args.domain)


if __name__ == "__main__":
    main()
