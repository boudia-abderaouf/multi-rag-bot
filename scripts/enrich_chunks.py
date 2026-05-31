"""
Enrichit chaque chunk avec des mots-clés et des questions hypothétiques,
puis re-embed et upsert dans Qdrant.

Principe : ajouter à la fin du texte du chunk les synonymes, notions connexes
et questions qu'un usager poserait → l'embedding devient sémantiquement plus
riche → les articles "distants" (ex: L413-2 / CIR pour "carte de séjour
temporaire") remontent dans le top-30.

Coût estimé : ~$0.70 pour 3522 chunks (GPT-4.1-mini, exécution unique).

Reprise automatique : les chunks déjà enrichis ("Notions connexes" dans le
texte) sont ignorés. Relancer le script reprend là où ça s'est arrêté.

Usage:
    python scripts/enrich_chunks.py                  # enrichit tout (reprend si interrompu)
    python scripts/enrich_chunks.py --dry-run        # aperçu sans écrire
    python scripts/enrich_chunks.py --limit 20       # test sur 20 chunks
    python scripts/enrich_chunks.py --batch-size 10  # nb chunks par appel GPT
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
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

# ── Prompt GPT ───────────────────────────────────────────────────────────────

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
    text = chunk["text"][:600]
    return f"Article : {aid}\n\n{text}"


# ── Appel GPT ────────────────────────────────────────────────────────────────

def generate_enrichments(client, chunks: list[dict], retry: int = 2) -> list[dict] | None:
    """Traite les chunks un par un avec json_object pour garantir un JSON valide."""
    results = []
    for chunk in chunks:
        user_prompt = build_user_prompt(chunk)
        success = False
        for attempt in range(retry + 1):
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=300,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                content = (response.choices[0].message.content or "").strip()
                obj = json.loads(content)
                if isinstance(obj, dict) and ("keywords" in obj or "questions" in obj):
                    results.append(obj)
                    success = True
                    break
            except Exception as exc:
                logger.warning(f"Erreur GPT chunk {chunk.get('chunk_index')} (tentative {attempt+1}) : {exc}")
                if attempt < retry:
                    time.sleep(2 ** attempt)
        if not success:
            results.append({})  # fallback : pas d'enrichissement pour ce chunk
    return results


# ── Formatage de l'enrichissement ────────────────────────────────────────────

def format_enrichment(enrichment: dict) -> str:
    keywords = enrichment.get("keywords") or []
    questions = enrichment.get("questions") or []
    parts = []
    if keywords:
        parts.append("Notions connexes: " + ", ".join(keywords))
    if questions:
        parts.append("Questions: " + " | ".join(questions))
    return " — ".join(parts)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Enrichit les chunks CESEDA avec mots-clés et questions.")
    parser.add_argument("--dry-run", action="store_true", help="Aperçu sans écrire dans Qdrant")
    parser.add_argument("--limit", type=int, default=0, help="Traiter seulement N chunks (0 = tous)")
    parser.add_argument("--batch-size", type=int, default=8, help="Chunks par appel GPT (défaut: 8)")
    parser.add_argument("--embed-batch", type=int, default=32, help="Chunks par appel embedding")
    args = parser.parse_args()

    if not CHUNKS_PATH.exists():
        logger.error(f"Fichier introuvable : {CHUNKS_PATH}")
        sys.exit(1)

    # ── Chargement de TOUS les chunks (jamais tronqué) ───────────────────────
    logger.info(f"Chargement des chunks depuis {CHUNKS_PATH}…")
    all_chunks: list[dict] = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_chunks.append(json.loads(line))
    logger.info(f"{len(all_chunks)} chunks chargés au total.")

    # ── Client OpenAI ─────────────────────────────────────────────────────────
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    embedder = OpenAIEmbedder.from_settings(settings)
    vector_store = QdrantVectorStore.from_settings(settings)

    # ── Reprise : ignorer les chunks déjà enrichis ────────────────────────────
    already_done = sum(1 for c in all_chunks if "Notions connexes" in c.get("text", ""))
    pending = [c for c in all_chunks if "Notions connexes" not in c.get("text", "")]
    if already_done:
        logger.info(f"{already_done} chunks déjà enrichis → ignorés. {len(pending)} restants.")

    # --limit restreint le nombre de chunks à TRAITER dans ce run, sans jamais
    # tronquer le fichier (all_chunks est toujours complet).
    to_process = pending[: args.limit] if args.limit else pending
    if args.limit and args.limit < len(pending):
        logger.info(f"--limit {args.limit} : traitement de {len(to_process)}/{len(pending)} chunks restants.")

    # ── Aperçu dry-run ────────────────────────────────────────────────────────
    if args.dry_run:
        sample = to_process[:5] if to_process else chunks[:5]
        enrichments = generate_enrichments(client, sample)
        print("\n── Exemples d'enrichissement ─────────────────────────────────────")
        for chunk, enr in zip(sample, enrichments or []):
            aid = chunk.get("metadata", {}).get("article_id", "?")
            suffix = format_enrichment(enr)
            print(f"\n[{aid}]")
            print(f"  Original  : {chunk['text'][:100]}…")
            print(f"  Enrichi   : …{(' — ' + suffix[:200]) if suffix else '(pas d enrichissement)'}")
        print(f"\nDry-run terminé. {len(to_process)} chunks à enrichir, {already_done} déjà faits/{len(all_chunks)} total.")
        return

    if not to_process:
        logger.info("Tous les chunks sont déjà enrichis.")
        return

    # ── Génération + sauvegarde + upsert en continu ───────────────────────────
    batch_size = args.batch_size
    n_batches = (len(to_process) + batch_size - 1) // batch_size
    n_errors = 0
    total_upserted = 0

    logger.info(f"Génération des enrichissements — {n_batches} batch(es) de {batch_size}…")

    for batch_idx in range(n_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(to_process))
        batch = to_process[start:end]

        enrichments = generate_enrichments(client, batch)

        if enrichments is None:
            logger.warning(f"Batch {batch_idx+1}/{n_batches} : échec total, texte original conservé.")
            n_errors += len(batch)
            continue

        # Appliquer les enrichissements sur les chunks
        enriched_batch = []
        for chunk, enr in zip(batch, enrichments):
            suffix = format_enrichment(enr)
            if suffix:
                chunk["text"] = chunk["text"] + " — " + suffix
            enriched_batch.append(chunk)
            if not suffix:
                n_errors += 1

        # ── Sauvegarde immédiate du fichier JSONL (TOUS les chunks) ──────────
        with CHUNKS_PATH.open("w", encoding="utf-8") as f:
            for c in all_chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        # ── Embedding + upsert immédiat de ce batch ───────────────────────────
        texts_batch = [c["text"] for c in enriched_batch]
        vectors_batch: list[list[float]] = []
        for i in range(0, len(texts_batch), args.embed_batch):
            vectors_batch.extend(embedder.embed_texts(texts_batch[i: i + args.embed_batch]))

        from collections import defaultdict
        by_collection: dict[str, list] = defaultdict(list)
        for chunk, vec in zip(enriched_batch, vectors_batch):
            coll = chunk.get("collection", "droit_etranger")
            by_collection[coll].append((chunk, vec))

        for collection_name, pairs in by_collection.items():
            for upsert_start in range(0, len(pairs), 100):
                sub = pairs[upsert_start: upsert_start + 100]
                vector_store.upsert_batch(
                    collection_name=collection_name,
                    records=[p[0] for p in sub],
                    vectors=[p[1] for p in sub],
                )
                total_upserted += len(sub)

        if (batch_idx + 1) % 10 == 0 or (batch_idx + 1) == n_batches:
            done_so_far = already_done + end
            logger.info(
                f"  {batch_idx + 1}/{n_batches} batches — "
                f"{done_so_far}/{len(all_chunks)} chunks enrichis — "
                f"{total_upserted} points upsertés"
            )

    logger.info(
        f"Enrichissement terminé : {total_upserted} upsertés, "
        f"{n_errors} sans enrichissement (texte original conservé)."
    )


if __name__ == "__main__":
    main()
