"""
Ré-ingestion propre du CESEDA depuis le PDF, avec :
  1. Filtrage des chunks "morts" (navigation/TOC/références courtes)
  2. Transfert de l'enrichissement depuis l'ancien ceseda.jsonl enrichi
  3. Enrichissement GPT des nouveaux chunks uniquement
  4. Upsert complet dans Qdrant (remplace toute la collection)

Usage:
    python scripts/reingest_clean.py --dry-run   # aperçu sans écrire
    python scripts/reingest_clean.py             # run complet
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))

from config.settings import settings
from ingestion.chunkers.article_chunker import ArticleChunker
from ingestion.embedders.openai_embedder import OpenAIEmbedder
from retrieval.vector_store import QdrantVectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PDF_PATH   = PROJECT_ROOT / "data" / "raw" / "ceseda.pdf"
OLD_CHUNKS = PROJECT_ROOT / "data" / "chunks" / "ceseda.jsonl"
NEW_CHUNKS = PROJECT_ROOT / "data" / "chunks" / "ceseda_clean.jsonl"
DOMAIN     = "droit_etranger"
COLLECTION = "droit_etranger"

# ── Patterns de chunks "morts" ────────────────────────────────────────────────
# Navigation entries: "Art. L. 532-1.- à L. 532-6" ou "et L. xxx" ou "La loi n° …"
_DEAD_BODY = re.compile(
    r"^(?:(?:à|et)\s+[LRD]\.\s+[\d\-]+|"          # "à L. 532-6" / "et L. 413-17"
    r"La loi n°\s+\d{4}-\d+\s+du\s+|"              # modification note
    r"[\d\-,\s]+[LRD]\.\s+[\d\-]+\s*$)",           # bare article list
    re.IGNORECASE,
)
_MIN_BODY_LEN = 80   # corps trop court → probablement navigation

# ── Prompt GPT (identique à enrich_chunks.py) ─────────────────────────────────
SYSTEM_PROMPT = """\
Tu es un expert en droit des étrangers (CESEDA). On te donne un extrait \
d'article de loi. Génère un objet JSON avec :
1. "keywords" : liste de 4-6 mots-clés ou notions juridiques connexes \
(synonymes, concepts liés, termes qu'un non-juriste utiliserait).
2. "questions" : liste de 2-3 questions précises qu'un usager pourrait \
poser et auxquelles cet article répond directement.

Réponds UNIQUEMENT avec l'objet JSON, sans commentaire."""


def build_user_prompt(chunk: dict) -> str:
    aid = chunk.get("metadata", {}).get("article_id", "?")
    return f"Article : {aid}\n\n{chunk['text'][:600]}"


def format_enrichment(enr: dict) -> str:
    kw = enr.get("keywords") or []
    qs = enr.get("questions") or []
    parts = []
    if kw:
        parts.append("Notions connexes: " + ", ".join(kw))
    if qs:
        parts.append("Questions: " + " | ".join(qs))
    return " — ".join(parts)


def enrich_one(client, chunk: dict, retry: int = 2) -> dict:
    for attempt in range(retry + 1):
        try:
            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(chunk)},
                ],
                max_tokens=300,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            obj = json.loads((resp.choices[0].message.content or "").strip())
            if isinstance(obj, dict) and ("keywords" in obj or "questions" in obj):
                return obj
        except Exception as exc:
            logger.warning(f"GPT erreur chunk {chunk.get('chunk_index')} tentative {attempt+1}: {exc}")
            if attempt < retry:
                time.sleep(2 ** attempt)
    return {}


def is_dead(chunk_text: str) -> bool:
    """Renvoie True si le chunk est une entrée de navigation sans contenu réel."""
    # Retire le préfixe article_id "Art. L. xxx-y.- " pour analyser le corps
    body = re.sub(r'^Art\.\s+[LRD]\.\s+[\d\-]+\.-\s*', '', chunk_text).strip()
    if len(body) < _MIN_BODY_LEN:
        return True
    if _DEAD_BODY.match(body):
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--embed-batch", type=int, default=32)
    args = parser.parse_args()

    # ── 1. Chargement des anciens chunks enrichis ──────────────────────────
    logger.info("Chargement des anciens chunks enrichis…")
    old_enriched: dict[str, str] = {}   # clé: article_id + body[:100] → suffix enrichi
    old_count = 0
    if OLD_CHUNKS.exists():
        with OLD_CHUNKS.open(encoding="utf-8") as f:
            for line in f:
                c = json.loads(line.strip())
                text = c.get("text", "")
                if "Notions connexes:" in text:
                    # Sépare texte original et enrichissement
                    idx = text.find(" — Notions connexes:")
                    base = text[:idx].strip()
                    suffix = text[idx:].strip()   # " — Notions connexes: …"
                    key = c["metadata"].get("article_id","") + "|" + base[:120]
                    old_enriched[key] = suffix
                    old_count += 1
    logger.info(f"{old_count} anciens enrichissements chargés.")

    # ── 2. Re-ingestion depuis le PDF ─────────────────────────────────────
    logger.info(f"Re-ingestion depuis {PDF_PATH}…")
    config_path = PROJECT_ROOT / "domains" / DOMAIN / "chunker_config.yaml"
    doc_metadata = {
        "domaine": DOMAIN,
        "source": "ceseda.pdf",
        "doc_id": "ceseda",
        "document_name": "Code de l'entrée et du séjour des étrangers et du droit d'asile (CESEDA)",
        "collection": COLLECTION,
    }
    chunker = ArticleChunker(config_path, doc_metadata)

    raw_chunks = list(chunker.chunk(PDF_PATH))
    logger.info(f"{len(raw_chunks)} chunks bruts extraits du PDF.")

    # ── 3. Filtrage des chunks morts ──────────────────────────────────────
    clean_chunks = []
    n_dead = 0
    for i, chunk in enumerate(raw_chunks):
        text = chunk.text
        if is_dead(text):
            n_dead += 1
            continue
        clean_chunks.append({
            "doc_id": "ceseda",
            "chunk_id": "",
            "chunk_index": i,
            "document_name": doc_metadata["document_name"],
            "collection": COLLECTION,
            "text": text,
            "metadata": chunk.metadata,
        })

    logger.info(f"{n_dead} chunks morts filtrés → {len(clean_chunks)} chunks valides.")

    # Recalculer chunk_id
    for c in clean_chunks:
        import hashlib
        c["chunk_id"] = hashlib.sha1(
            (c["doc_id"] + str(c["chunk_index"]) + c["text"][:200]).encode()
        ).hexdigest()

    if args.dry_run:
        print(f"\nDry-run : {len(clean_chunks)} chunks valides, {n_dead} filtrés.")
        print("\nExemples de chunks valides:")
        for c in clean_chunks[:5]:
            print(f"  [{c['metadata']['article_id']}] {c['text'][:100]}…")
        return

    # ── 4. Transfert enrichissement + GPT pour les nouveaux ──────────────
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    n_reused = 0
    n_new_enrich = 0
    n_errors = 0

    for c in clean_chunks:
        if "Notions connexes:" in c["text"]:
            n_reused += 1
            continue

        key = c["metadata"].get("article_id","") + "|" + c["text"][:120]
        if key in old_enriched:
            c["text"] = c["text"] + " " + old_enriched[key]
            n_reused += 1
        else:
            # Nouveau chunk → enrichissement GPT
            enr = enrich_one(client, c)
            suffix = format_enrichment(enr)
            if suffix:
                c["text"] = c["text"] + " — " + suffix
            else:
                n_errors += 1
            n_new_enrich += 1
            if n_new_enrich % 50 == 0:
                logger.info(f"  {n_new_enrich} nouveaux chunks enrichis…")

    logger.info(
        f"Enrichissement : {n_reused} réutilisés, {n_new_enrich} nouveaux, "
        f"{n_errors} sans enrichissement."
    )

    # ── 5. Sauvegarde JSONL ───────────────────────────────────────────────
    logger.info(f"Sauvegarde dans {NEW_CHUNKS}…")
    with NEW_CHUNKS.open("w", encoding="utf-8") as f:
        for c in clean_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # Remplace l'ancien fichier
    import shutil
    shutil.copy(NEW_CHUNKS, OLD_CHUNKS)
    logger.info("ceseda.jsonl remplacé par la version propre.")

    # ── 6. Re-embedding + upsert Qdrant ───────────────────────────────────
    embedder = OpenAIEmbedder.from_settings(settings)
    vector_store = QdrantVectorStore.from_settings(settings)

    texts = [c["text"] for c in clean_chunks]
    logger.info(f"Embedding de {len(texts)} chunks…")

    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), args.embed_batch):
        all_vectors.extend(embedder.embed_texts(texts[i: i + args.embed_batch]))
        if (i // args.embed_batch + 1) % 20 == 0:
            logger.info(f"  {len(all_vectors)}/{len(texts)} vecteurs…")

    logger.info(f"{len(all_vectors)} vecteurs générés. Upsert dans Qdrant…")

    # Vider la collection et ré-upserter proprement
    from qdrant_client import QdrantClient
    qdrant = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    logger.info(f"Suppression de l'ancienne collection '{COLLECTION}'…")
    try:
        qdrant.delete_collection(COLLECTION)
        logger.info("Collection supprimée.")
    except Exception as e:
        logger.warning(f"Suppression impossible : {e}")

    total_upserted = 0
    for start in range(0, len(clean_chunks), 100):
        batch_c = clean_chunks[start: start + 100]
        batch_v = all_vectors[start: start + 100]
        vector_store.upsert_batch(
            collection_name=COLLECTION,
            records=batch_c,
            vectors=batch_v,
        )
        total_upserted += len(batch_c)
        if (start // 100 + 1) % 10 == 0:
            logger.info(f"  {total_upserted}/{len(clean_chunks)} upsertés…")

    logger.info(f"✅ Re-indexation terminée : {total_upserted} points dans Qdrant.")


if __name__ == "__main__":
    main()
