"""
Script d'ingestion — à lancer manuellement ou via un job schedulé.
 
Usage :
    python scripts/ingest.py --domain droit_etranger
"""
import argparse
import logging
import sys
from pathlib import Path
 
# Ajoute la racine du projet au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
 
from ingestion.pipeline import run_ingestion
 
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