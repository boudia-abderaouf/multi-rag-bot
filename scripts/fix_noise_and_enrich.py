"""
Fix two things in one pass:
  1. Remove navigation noise from all chunks (service-public.fr, Bulletin, etc.)
  2. Override/augment enrichment for key articles with targeted vocabulary
  3. Re-embed ONLY changed chunks and upsert to Qdrant

Usage:
    python scripts/fix_noise_and_enrich.py --dry-run   # preview, no writes
    python scripts/fix_noise_and_enrich.py             # full fix
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
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


# ── 1. Nettoyage du bruit de navigation ─────────────────────────────────────

def clean_chunk_text(text: str) -> str:
    """Retire le bruit PDF : breadcrumbs service-public, Bulletins, Legifrance tags, titres structurels."""
    # service-public.fr breadcrumb (toute la ligne jusqu'à un saut de ligne ou fin de texte)
    text = re.sub(r'\s*service-public\.fr\s*>[^\n]*', '', text)

    # "Récemment au Bulletin …" footer (inclut les entrées > … qui suivent)
    text = re.sub(r'\s*Récemment au Bulletin[^\n]*(?:\n\s*>[^\n]*)*', '', text, flags=re.IGNORECASE)

    # Cross-refs Legifrance / jurisprudence
    text = re.sub(
        r'\s*(?:Legif\.|Jp\.Judi\.|Jp\.Admin\.|Juricaf|Conseil Constit\.|QPC)\s*[^.|\n]*',
        '', text,
    )

    # "Chapitre X : …" / "Section N : …" headings inline
    text = re.sub(r'\s*(?:Chapitre\s+[IVX\d]+[^:]*:|Section\s+\d+\s*:)[^\n]*', '', text)

    # "Du Titre …" / "Au Titre …" navigation
    text = re.sub(r'\s*[AaDd]u\s+[Tt]itre\s+[IVX]+[^\n]*', '', text)

    # "Application de plein droit …" navigation
    text = re.sub(r'\s*Application de plein droit[^\n]*', '', text)

    # ALL-CAPS structural headings (TITRE, CHAPITRE, SECTION)
    text = re.sub(
        r'\s+(?:TITRE|CHAPITRE|SECTION)\s+[IVX\d]+\s*[:\-]?\s*[A-ZÉÀÙ][^\n]{0,120}',
        '', text, flags=re.MULTILINE,
    )

    # Collapse extra whitespace
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


# ── 2. Enrichissements ciblés ────────────────────────────────────────────────
# Clé = article_id exact dans le JSONL
# Valeur = nouveau suffixe complet (remplace le suffixe existant)

TARGETED_ENRICHMENTS: dict[str, str] = {
    # Q016 rank 31 — "expulsion vs OQTF" : vocabulaire trop spécifique
    "Art. L. 631-2": (
        "Notions connexes: procédure d'expulsion, arrêté d'expulsion, distinction OQTF expulsion, "
        "mesure d'éloignement, ordre public nécessité impérieuse, expulsion administrative, "
        "protection contre l'expulsion, sûreté de l'État — "
        "Questions: Quelle est la procédure pour expulser un étranger ? | "
        "Quelle différence entre une expulsion et une OQTF ? | "
        "Qui peut être expulsé pour nécessité impérieuse pour la sûreté de l'État ?"
    ),

    # Q017/Q018 rank 33/66 — "régularisation" : enrichissement ne mentionne pas régularisation
    "Art. L. 435-3": (
        "Notions connexes: régularisation jeune étranger, admission exceptionnelle au séjour ASE, "
        "sans-papiers mineur isolé confié aide sociale enfance, titre de séjour jeune majeur, "
        "régularisation formation professionnelle, mineur non accompagné majorité, MNA régularisation — "
        "Questions: Comment régulariser un jeune étranger confié à l'ASE ? | "
        "Un mineur non accompagné peut-il être régularisé à sa majorité ? | "
        "Quelles conditions pour l'admission exceptionnelle au séjour d'un jeune suivi par l'ASE ?"
    ),

    # Q008 rank 37 — "contester refus OFPRA" : chunk parle de convention de Genève spécifiquement
    "Art. L. 532-4": (
        "Notions connexes: recours CNDA contre refus OFPRA, appel rejet demande asile, "
        "contester décision OFPRA, procédure CNDA réfugiés, délai recours asile, "
        "cour nationale droit d'asile convention de Genève, recours protection subsidiaire — "
        "Questions: Comment contester un refus de l'OFPRA devant la CNDA ? | "
        "Dans quel délai faire appel d'une décision de l'OFPRA ? | "
        "Quelle procédure devant la CNDA pour les réfugiés de la convention de Genève ?"
    ),

    # Q009 rank 42 — "obligations DA" : "risque de fuite" vocabulaire trop spécifique
    "Art. L. 523-2": (
        "Notions connexes: obligations demandeur d'asile, manquements procédure asile, "
        "risque de fuite demandeur asile, clôture demande asile comportement, "
        "assignation résidence asile, rétention demandeur asile, non-présentation OFPRA — "
        "Questions: Quels manquements d'un demandeur d'asile justifient la clôture de sa demande ? | "
        "Dans quels cas un demandeur d'asile peut-il être placé en rétention ? | "
        "Quelles obligations s'imposent à un demandeur d'asile pendant l'instruction ?"
    ),

    # Q008 rank 217 — recours CNDA principal : chunk tronqué + mauvais enrichissement
    "Art. L. 532-1": (
        "Notions connexes: recours contre décision OFPRA, cour nationale droit d'asile CNDA, "
        "contester refus asile, appel rejet réfugié protection subsidiaire, "
        "recours juridictionnel asile, CNDA compétence, voies de recours asile — "
        "Questions: Quel recours contre un refus de l'OFPRA ? | "
        "Comment contester une décision de l'OFPRA sur le statut de réfugié ? | "
        "Devant quelle juridiction contester un refus d'asile ?"
    ),

    # Q006 — L121-7 est le vrai article OFPRA dans notre PDF (L121-1 = OFII)
    "Art. L. 121-7": (
        "Notions connexes: OFPRA définition rôle, Office français de protection des réfugiés et apatrides, "
        "missions OFPRA asile, statut réfugié protection subsidiaire apatride, "
        "établissement public OFPRA, procédure asile France, instruction demande protection — "
        "Questions: Qu'est-ce que l'OFPRA et quel est son rôle ? | "
        "Quel est le rôle de l'Office français de protection des réfugiés et apatrides ? | "
        "Quelles sont les missions de l'OFPRA dans la procédure d'asile ?"
    ),

    # Q006 rank 119 — "rôle OFPRA" : chunk parle d'enregistrement + Dublin, pas du rôle OFPRA
    "Art. L. 521-1": (
        "Notions connexes: rôle OFPRA procédure asile, enregistrement demande asile OFPRA, "
        "dépôt demande asile, instruction asile office français protection réfugiés, "
        "OFPRA compétence, demande protection internationale, guichet unique asile — "
        "Questions: Quel est le rôle de l'OFPRA dans la procédure d'asile ? | "
        "Comment déposer une demande d'asile à l'OFPRA ? | "
        "Comment fonctionne l'enregistrement d'une demande d'asile ?"
    ),

    # Q001 rank ABSENT — CIR première délivrance
    "Art. L. 413-2": (
        "Notions connexes: contrat d'intégration républicaine CIR, première carte de séjour, "
        "parcours intégration étranger primo-arrivant, obligations intégration, "
        "formation civique linguistique arrivant, premier titre de séjour conditions, "
        "intégration républicaine nouveau résident — "
        "Questions: Qu'est-ce que le contrat d'intégration républicaine (CIR) ? | "
        "Quelles obligations d'intégration pour la première carte de séjour ? | "
        "Un étranger qui arrive pour la première fois doit-il signer un contrat d'intégration ?"
    ),

    # Q004 rank 106 — CSP durée 4 ans
    "Art. L. 411-3": (
        "Notions connexes: durée carte de séjour pluriannuelle CSP, validité titre de séjour, "
        "renouvellement carte pluriannuelle 4 ans, durée visa long séjour, "
        "titre pluriannuel premier renouvellement, durée maximale autorisation séjour — "
        "Questions: Quelle est la durée d'une carte de séjour pluriannuelle ? | "
        "Combien de temps est valable une carte de séjour temporaire ? | "
        "Quand peut-on obtenir une carte de séjour pluriannuelle de 4 ans ?"
    ),

    # Q030 rank ABSENT — droit au travail attaché au titre
    "Art. L. 414-1": (
        "Notions connexes: autorisation de travail étranger, droit travail titre de séjour, "
        "étranger salarié activité professionnelle, emploi étranger carte de séjour, "
        "exercice activité professionnelle salariée, travail légal étranger France — "
        "Questions: Un étranger peut-il travailler avec un titre de séjour ? | "
        "Quelles conditions pour qu'un étranger obtienne une autorisation de travail ? | "
        "Un titre de séjour donne-t-il automatiquement le droit de travailler ?"
    ),

    # Q034 rank 386 — vie privée et familiale ancienneté résidence
    "Art. L. 423-23": (
        "Notions connexes: vie privée familiale ancienneté résidence, régularisation 10 ans, "
        "étranger longue durée France séjour irrégulier, carte séjour vie privée liens personnels, "
        "CEDH article 8 vie privée étranger, régularisation par la vie privée et familiale, "
        "ancienneté présence France titre de séjour — "
        "Questions: Un étranger présent depuis 10 ans en France peut-il se régulariser ? | "
        "Quels critères pour obtenir un titre de séjour vie privée et familiale ? | "
        "Comment l'ancienneté de résidence influence-t-elle la demande de titre de séjour ?"
    ),

    # Q033 rank ABSENT — transfert Dublin
    "Art. L. 572-2": (
        "Notions connexes: transfert Dublin État responsable asile, décision transfert délai, "
        "règlement Dublin III transfert étranger, exécution décision transfert, "
        "assignation résidence Dublin, rétention transfert Dublin, délai transfert 15 jours — "
        "Questions: Comment s'exécute un transfert Dublin vers un autre État ? | "
        "Dans quel délai une décision de transfert Dublin peut-elle être exécutée ? | "
        "Peut-on contester une décision de transfert Dublin ?"
    ),

    # Q035 rank 279 — délai de départ volontaire réduction
    "Art. L. 612-3": (
        "Notions connexes: réduction délai départ volontaire OQTF, suppression délai départ, "
        "risque de fuite OQTF délai, cas départ immédiat sans délai, "
        "délai départ volontaire conditions refus, comportement étranger OQTF — "
        "Questions: Dans quels cas le délai de départ volontaire peut-il être supprimé ? | "
        "Un étranger peut-il demander un délai pour partir après une OQTF ? | "
        "Quelles conditions pour la réduction du délai de départ volontaire ?"
    ),
}


# ── Main ─────────────────────────────────────────────────────────────────────

def _strip_enrichment(text: str) -> str:
    """Retire le suffixe d'enrichissement existant (commence par ' — Notions connexes:')."""
    idx = text.find(" — Notions connexes:")
    if idx == -1:
        idx = text.find("— Notions connexes:")
    return text[:idx].strip() if idx != -1 else text.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--embed-batch", type=int, default=32)
    args = parser.parse_args()

    # ── Chargement ───────────────────────────────────────────────────────────
    logger.info(f"Chargement de {CHUNKS_PATH}…")
    all_chunks: list[dict] = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_chunks.append(json.loads(line))
    logger.info(f"{len(all_chunks)} chunks chargés.")

    # ── Application des fixes ─────────────────────────────────────────────
    changed_indices: list[int] = []
    n_noise_fixed = 0
    n_enrich_fixed = 0

    for i, chunk in enumerate(all_chunks):
        original_text = chunk["text"]
        article_id = chunk.get("metadata", {}).get("article_id", "")

        # Séparer corps + enrichissement existant
        body = _strip_enrichment(original_text)
        cleaned_body = clean_chunk_text(body)

        # Choisir l'enrichissement : ciblé ou existant
        if article_id in TARGETED_ENRICHMENTS:
            enrich_suffix = " — " + TARGETED_ENRICHMENTS[article_id]
            n_enrich_fixed += 1
        else:
            # Garder l'enrichissement existant (si présent)
            idx = original_text.find(" — Notions connexes:")
            if idx == -1:
                idx = original_text.find("— Notions connexes:")
            enrich_suffix = (" " + original_text[idx:].strip()) if idx != -1 else ""

        new_text = cleaned_body + enrich_suffix

        if new_text != original_text:
            chunk["text"] = new_text
            changed_indices.append(i)
            if cleaned_body != body:
                n_noise_fixed += 1

    logger.info(
        f"Modifications : {len(changed_indices)} chunks modifiés "
        f"({n_noise_fixed} nettoyages bruit, {n_enrich_fixed} enrichissements ciblés)."
    )

    if args.dry_run:
        print(f"\nDry-run — {len(changed_indices)} chunks seraient modifiés.")
        # Afficher les articles ciblés
        print("\n── Enrichissements ciblés ──────────────────────────────────────")
        for i, chunk in enumerate(all_chunks):
            aid = chunk.get("metadata", {}).get("article_id", "")
            if aid in TARGETED_ENRICHMENTS and i in changed_indices:
                body = _strip_enrichment(chunk["text"])
                print(f"\n  [{aid}]")
                print(f"  Corps : {body[:120]}…")
                print(f"  Nouv. : {TARGETED_ENRICHMENTS[aid][:120]}…")
        # Afficher quelques exemples de bruit nettoyé
        print("\n── Exemples de bruit nettoyé ──────────────────────────────────")
        noise_shown = 0
        for i in changed_indices:
            if noise_shown >= 5:
                break
            chunk = all_chunks[i]
            aid = chunk.get("metadata", {}).get("article_id", "")
            if aid not in TARGETED_ENRICHMENTS:
                print(f"\n  [{aid}] {repr(chunk['text'][:200])}")
                noise_shown += 1
        return

    # ── Sauvegarde JSONL ─────────────────────────────────────────────────
    logger.info("Sauvegarde du JSONL…")
    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    logger.info(f"JSONL sauvegardé ({len(all_chunks)} chunks).")

    if not changed_indices:
        logger.info("Aucun chunk modifié. Rien à re-embedder.")
        return

    # ── Re-embedding des chunks modifiés uniquement ──────────────────────
    changed_chunks = [all_chunks[i] for i in changed_indices]
    texts = [c["text"] for c in changed_chunks]

    embedder = OpenAIEmbedder.from_settings(settings)
    vector_store = QdrantVectorStore.from_settings(settings)

    logger.info(f"Embedding de {len(texts)} chunks modifiés (batch={args.embed_batch})…")
    all_vectors: list[list[float]] = []
    for start in range(0, len(texts), args.embed_batch):
        batch = texts[start: start + args.embed_batch]
        all_vectors.extend(embedder.embed_texts(batch))
        if (start // args.embed_batch + 1) % 10 == 0:
            logger.info(f"  {len(all_vectors)}/{len(texts)} vecteurs…")

    logger.info(f"{len(all_vectors)} vecteurs générés. Upsert dans Qdrant…")

    by_collection: dict[str, list] = defaultdict(list)
    for chunk, vec in zip(changed_chunks, all_vectors):
        coll = chunk.get("collection", "droit_etranger")
        by_collection[coll].append((chunk, vec))

    total_upserted = 0
    for collection_name, pairs in by_collection.items():
        for start in range(0, len(pairs), 100):
            sub = pairs[start: start + 100]
            vector_store.upsert_batch(
                collection_name=collection_name,
                records=[p[0] for p in sub],
                vectors=[p[1] for p in sub],
            )
            total_upserted += len(sub)

    logger.info(f"✅ Terminé : {total_upserted} points mis à jour dans Qdrant.")


if __name__ == "__main__":
    main()
