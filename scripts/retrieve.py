import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))

from retrieval.retriever import Retriever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    parser = argparse.ArgumentParser(description="Interroge une collection Qdrant pour un domaine.")
    parser.add_argument("--domain", required=True, help="Nom du domaine, ex: droit_etranger")
    parser.add_argument("--question", required=True, help="Question utilisateur")
    parser.add_argument(
        "--collection",
        default=None,
        help="Collection Qdrant a interroger. Par defaut, reutilise le nom du domaine.",
    )
    parser.add_argument("--limit", type=int, default=5, help="Nombre de chunks a retourner")
    args = parser.parse_args()

    retriever = Retriever()
    collection_name = args.collection or args.domain
    hits = retriever.retrieve(
        collection_name=collection_name,
        query=args.question,
        limit=args.limit,
    )
    prompt = retriever.build_prompt(domain=args.domain, question=args.question, hits=hits)

    print("=== HITS ===")
    for hit in hits:
        article_id = hit.payload.get("metadata", {}).get("article_id", "article inconnu")
        print(f"- score={hit.score:.4f} article={article_id}")

    print("\n=== PROMPT ===")
    print(prompt)


if __name__ == "__main__":
    main()
