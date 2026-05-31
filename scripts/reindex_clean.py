"""
Re-index CESEDA chunks after cleaning PDF navigation noise from texts.

Reads data/chunks/ceseda.jsonl, strips service-public.fr links / chapter
headers / navigation breadcrumbs from each chunk text, re-embeds with
OpenAI and upserts back to Qdrant (same point_id ⇒ in-place update).

Usage:
    python scripts/reindex_clean.py                  # full re-index
    python scripts/reindex_clean.py --dry-run        # preview cleaning only, no writes
    python scripts/reindex_clean.py --batch-size 64  # override embed batch size
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
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


# ── Cleaning function ──────────────────────────────────────────────────────────

def clean_chunk_text(text: str) -> str:
    """Strip PDF navigation noise injected during extraction.

    Patterns removed:
    - service-public.fr breadcrumb links  (e.g. "service-public.fr > Etrangers…")
    - "Récemment au Bulletin …" footers
    - Legifrance / jurisprudence cross-ref tags  (Legif. | Jp.Judi. | Juricaf …)
    - Structural headings that are not article content
      (Chapitre … : …  /  Section N :  /  Du Titre … /  TITRE … / CHAPITRE … / SECTION …)
    - "Application de plein droit …" navigation lines
    - Double / triple spaces left behind
    """
    # service-public.fr breadcrumb
    text = re.sub(r'\s*service-public\.fr\s*>[^.\n]*\.?', '', text)

    # "Récemment au Bulletin …" footer
    text = re.sub(r'\s*Récemment au Bulletin[^>]*>[^\n]*', '', text, flags=re.IGNORECASE)

    # Cross-reference tags from Legifrance sidebar
    text = re.sub(
        r'\s*(?:Legif\.|Jp\.Judi\.|Jp\.Admin\.|Juricaf|Conseil Constit\.|QPC)\s*[^.|\n]*',
        '',
        text,
    )

    # Chapter / section structural headings (noise between articles)
    text = re.sub(r'\s*(?:Chapitre [IVX]+[^:]*:|Section \d+\s*:)[^\n]*', '', text)

    # "Du Titre …" / "Au Titre …" navigation lines
    text = re.sub(r'\s*[AaDd]u\s+[Tt]itre\s+[IVX]+[^\n]*', '', text)

    # "Application de plein droit …" navigation lines
    text = re.sub(r'\s*Application de plein droit[^\n]*', '', text)

    # ALL-CAPS structural headings (TITRE, CHAPITRE, SECTION + title text)
    text = re.sub(
        r'\s+(?:TITRE|CHAPITRE|SECTION)\s+[IVX\d]+\s*[:\-]?\s*[A-ZÉÀÙ][^\n]{0,100}',
        '',
        text,
        flags=re.MULTILINE,
    )

    # Collapse extra whitespace
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Re-embed CESEDA chunks after text cleaning.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print cleaning stats without writing to Qdrant")
    parser.add_argument("--batch-size", type=int, default=32,
                        help="Number of chunks to embed per OpenAI call (default: 32)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process first N chunks (0 = all, useful for testing)")
    args = parser.parse_args()

    if not CHUNKS_PATH.exists():
        logger.error(f"Fichier introuvable : {CHUNKS_PATH}")
        sys.exit(1)

    # ── Load chunks ──────────────────────────────────────────────────────────
    logger.info(f"Chargement des chunks depuis {CHUNKS_PATH} …")
    chunks: list[dict] = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    if args.limit:
        chunks = chunks[: args.limit]

    logger.info(f"{len(chunks)} chunks chargés.")

    # ── Apply cleaning ───────────────────────────────────────────────────────
    n_changed = 0
    n_empty_after = 0
    for chunk in chunks:
        original = chunk["text"]
        cleaned = clean_chunk_text(original)
        if cleaned != original:
            n_changed += 1
        if not cleaned:
            n_empty_after += 1
            logger.warning(f"  chunk_index={chunk['chunk_index']} vide après nettoyage — conserve le texte original")
            cleaned = original
        chunk["text"] = cleaned

    logger.info(
        f"Nettoyage terminé : {n_changed}/{len(chunks)} chunks modifiés"
        f"{', ' + str(n_empty_after) + ' conservés (vides après nettoyage)' if n_empty_after else ''}."
    )

    if args.dry_run:
        # Show a few examples
        examples = [c for c in chunks if len(c["text"]) < len(clean_chunk_text.__doc__ or "") or True]
        # Print 5 random changed ones
        changed = [c for c in chunks if clean_chunk_text(c["text"]) != c["text"]][:5]
        print("\n── Exemples de chunks nettoyés ────────────────────────────────────")
        shown = 0
        for c in chunks:
            if shown >= 5:
                break
            orig_text = c["text"]  # already cleaned in-place above, show as-is
            print(f"\n  [{c['metadata'].get('article_id', '?')}]  (index {c['chunk_index']})")
            print(f"  → {repr(c['text'][:200])}")
            shown += 1
        print(f"\nDry-run terminé. {n_changed} chunks auraient été re-indexés.")
        return

    # ── Embed ────────────────────────────────────────────────────────────────
    embedder = OpenAIEmbedder.from_settings(settings)
    embedder.batch_size = args.batch_size
    vector_store = QdrantVectorStore.from_settings(settings)

    texts = [c["text"] for c in chunks]
    logger.info(f"Génération des embeddings pour {len(texts)} chunks (batch={args.batch_size}) …")

    all_vectors: list[list[float]] = []
    batch_count = 0
    for i in range(0, len(texts), args.batch_size):
        batch_texts = texts[i : i + args.batch_size]
        batch_vecs = embedder.embed_texts(batch_texts)
        all_vectors.extend(batch_vecs)
        batch_count += 1
        if batch_count % 10 == 0:
            logger.info(f"  {len(all_vectors)}/{len(texts)} vecteurs générés …")

    logger.info(f"Embeddings générés : {len(all_vectors)} vecteurs.")

    # ── Upsert to Qdrant ─────────────────────────────────────────────────────
    # Group by collection (all ceseda chunks go to 'droit_etranger')
    from collections import defaultdict
    by_collection: dict[str, list[tuple[dict, list[float]]]] = defaultdict(list)
    for chunk, vec in zip(chunks, all_vectors):
        coll = chunk.get("collection", "droit_etranger")
        by_collection[coll].append((chunk, vec))

    upsert_batch_size = 100
    total_upserted = 0

    for collection_name, pairs in by_collection.items():
        logger.info(f"Upsert dans '{collection_name}' ({len(pairs)} points) …")
        for start in range(0, len(pairs), upsert_batch_size):
            batch_pairs = pairs[start : start + upsert_batch_size]
            records = [p[0] for p in batch_pairs]
            vectors = [p[1] for p in batch_pairs]
            vector_store.upsert_batch(
                collection_name=collection_name,
                records=records,
                vectors=vectors,
            )
            total_upserted += len(records)
            if (start // upsert_batch_size + 1) % 5 == 0:
                logger.info(f"  {total_upserted}/{len(pairs)} upsertés …")

    logger.info(f"Re-indexation terminée : {total_upserted} points upsertés dans Qdrant.")


if __name__ == "__main__":
    main()
