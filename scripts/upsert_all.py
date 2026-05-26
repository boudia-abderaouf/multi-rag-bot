"""
Re-embed et upsert TOUS les chunks depuis ceseda.jsonl vers Qdrant.
Utilise des batches de 50 avec retry (5 tentatives) pour éviter les timeouts.

Usage:
    python scripts/upsert_all.py              # tous les chunks
    python scripts/upsert_all.py --limit 100  # test sur 100 chunks
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))

from config.settings import settings
from ingestion.embedders.openai_embedder import OpenAIEmbedder
from retrieval.vector_store import QdrantVectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks" / "ceseda.jsonl"


def upsert_with_retry(
    vector_store: QdrantVectorStore,
    collection_name: str,
    records: list,
    vectors: list,
    max_attempts: int = 5,
) -> None:
    for attempt in range(max_attempts):
        try:
            vector_store.upsert_batch(
                collection_name=collection_name,
                records=records,
                vectors=vectors,
            )
            return
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning(
                f"Upsert tentative {attempt+1}/{max_attempts} échouée : {exc.__class__.__name__}. "
                f"Retry dans {wait}s…"
            )
            if attempt < max_attempts - 1:
                time.sleep(wait)
    raise RuntimeError(f"Upsert échoué après {max_attempts} tentatives.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--embed-batch", type=int, default=32)
    parser.add_argument("--upsert-batch", type=int, default=50)
    args = parser.parse_args()

    # ── Chargement ───────────────────────────────────────────────────────
    logger.info(f"Chargement de {CHUNKS_PATH}…")
    chunks: list[dict] = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    if args.limit:
        chunks = chunks[: args.limit]
    logger.info(f"{len(chunks)} chunks à indexer.")

    # ── Embedding ────────────────────────────────────────────────────────
    embedder = OpenAIEmbedder.from_settings(settings)
    vector_store = QdrantVectorStore.from_settings(settings)

    texts = [c["text"] for c in chunks]
    logger.info(f"Embedding de {len(texts)} chunks (batch={args.embed_batch})…")

    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), args.embed_batch):
        batch = texts[i: i + args.embed_batch]
        all_vectors.extend(embedder.embed_texts(batch))
        if (i // args.embed_batch + 1) % 10 == 0:
            logger.info(f"  {len(all_vectors)}/{len(texts)} vecteurs…")

    logger.info(f"{len(all_vectors)} vecteurs générés.")

    # ── Upsert avec retry ────────────────────────────────────────────────
    by_collection: dict[str, list] = defaultdict(list)
    for chunk, vec in zip(chunks, all_vectors):
        coll = chunk.get("collection", "droit_etranger")
        by_collection[coll].append((chunk, vec))

    total_upserted = 0
    for collection_name, pairs in by_collection.items():
        logger.info(f"Upsert dans '{collection_name}' ({len(pairs)} points, batch={args.upsert_batch})…")
        for start in range(0, len(pairs), args.upsert_batch):
            sub = pairs[start: start + args.upsert_batch]
            upsert_with_retry(
                vector_store,
                collection_name,
                records=[p[0] for p in sub],
                vectors=[p[1] for p in sub],
            )
            total_upserted += len(sub)
            if (start // args.upsert_batch + 1) % 10 == 0:
                logger.info(f"  {total_upserted}/{len(pairs)} upsertés…")

    logger.info(f"✅ Terminé : {total_upserted} points dans Qdrant.")


if __name__ == "__main__":
    main()
