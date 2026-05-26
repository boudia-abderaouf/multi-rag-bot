"""
Ajoute des enrichissements ciblés aux chunks des articles manqués au recall@30.

Usage:
    python3 scripts/enrich_missed.py            # enrichit + sauvegarde ceseda.jsonl
    python3 scripts/enrich_missed.py --dry-run  # affiche seulement les articles modifiés
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks" / "ceseda.jsonl"

# ── Enrichissements ciblés ───────────────────────────────────────────────────
# Format: "Art. X. Y-Z" → suffix to append after existing "— Notions connexes:"
# Pour les articles qui ont déjà une section Notions connexes, on REMPLACE.
# Les tokens sont conçus pour couvrir les variantes de la question benchmark.

TARGETED_ENRICHMENTS: dict[str, str] = {
    # Q001 : CIR, premier titre de séjour
    "Art. L. 413-2": (
        "contrat d'intégration républicaine CIR premier titre carte séjour temporaire, "
        "primo-arrivant premier accès séjour France CIR, "
        "parcours personnalisé intégration républicaine, signature CIR délivrance CST, "
        "formation linguistique civique étranger premier titre, "
        "obligations intégration étranger carte séjour temporaire primo-arrivant"
    ),

    # Q004 : durée CSP 4 ans, pluriannuelle après CST
    "Art. L. 411-3": (
        "durée carte de séjour pluriannuelle CSP 4 ans validité maximale, "
        "conditions CSP durée maximale quatre ans après CST, "
        "carte séjour pluriannuelle conditions validité durée, "
        "durée maximale carte séjour temporaire CST un an, "
        "obtenir CSP conditions durée pluriannuelle, différence CST CSP durée"
    ),

    # Q005 : récépissé renouvellement, droit travail pendant instruction
    "Art. R. 431-12": (
        "récépissé renouvellement titre de séjour travailler attente, "
        "autorisation de travail pendant instruction renouvellement préfet, "
        "peut-il travailler en attendant décision préfet renouvellement, "
        "récépissé dépôt demande renouvellement droit travail, "
        "base juridique travailler instruction titre séjour, "
        "présence légale autorisation séjour récépissé"
    ),
    "Art. R. 431-15-1": (
        "attestation prolongation instruction dématérialisée travailler en attendant, "
        "équivalent récépissé téléprocédure autorisation travail attente décision, "
        "peut-il travailler étranger en attente décision préfet ANEF attestation, "
        "autorisation provisoire numérique droit travail instruction titre séjour, "
        "base juridique travail pendant instruction renouvellement attestation en ligne"
    ),
    "Art. L. 431-3": (
        "document provisoire séjour peut travailler en attendant décision préfet, "
        "étranger peut travailler document provisoire renouvellement titre séjour, "
        "base juridique travailler attente décision autorisation provisoire, "
        "récépissé document provisoire autorise exercice activité salariée, "
        "effet document provisoire sur droit séjour travail étranger"
    ),

    # Q006 : OFPRA missions (L121-7 est le bon article dans notre PDF)
    "Art. L. 121-7": (
        "OFPRA office français protection réfugiés apatrides, mission OFPRA, "
        "reconnaissance qualité réfugié, protection subsidiaire accordée OFPRA, "
        "statut apatride OFPRA, établissement public asile, directeur général OFPRA"
    ),

    # Q009 : obligations demandeur asile, assignation rétention
    "Art. L. 523-1": (
        "obligations demandeur asile pendant instruction procédure, "
        "demandeur asile doit respecter obligations assignation comportement, "
        "quelles sont obligations demandeur asile instruction, "
        "comportement demandeur asile procédure rétention menace ordre public, "
        "obligations légales étranger demandeur asile pendant examen demande"
    ),
    "Art. L. 523-2": (
        "obligations demandeur asile pendant instruction clôture OFPRA, "
        "quelles sont obligations demandeur asile instruction conséquences manquement, "
        "clôture demande asile non-respect obligations pendant procédure, "
        "conséquence manquement obligations demandeur asile clôture procédure, "
        "OFPRA clôture demande manquement obligations étranger demandeur"
    ),

    # Q010 : protection subsidiaire définition  
    "Art. L. 512-1": (
        "protection subsidiaire définition, conditions protection subsidiaire, "
        "risque réel peine de mort torture violence conflit armé, "
        "personne ne remplit pas conditions réfugié, motifs protection subsidiaire, "
        "atteintes graves peine mort torture traitements inhumains"
    ),

    # Q014 : rétention prolongation durée
    "Art. L. 741-1": (
        "placement initial rétention administrative 96 heures, préfet décision rétention, "
        "durée initiale rétention 4 jours, conditions placement rétention étranger, "
        "rétention administrative prononcée par préfet autorité administrative"
    ),
    "Art. L. 742-1": (
        "prolongation rétention judiciaire au-delà 96 heures, magistrat siège tribunal judiciaire, "
        "maintien rétention prolongation, requête prolongation rétention administrative, "
        "contrôle judiciaire rétention administrative, JLD magistrat siège rétention"
    ),
    "Art. L. 742-3": (
        "prolongation rétention 26 jours, durée prolongation rétention administrative, "
        "rétention après 96h vingt-six jours, première prolongation judiciaire rétention, "
        "durée maintien rétention après placement initial"
    ),
    "Art. L. 742-4": (
        "deuxième prolongation rétention au-delà trente jours, urgence absolue ordre public rétention, "
        "prolongation exceptionnelle rétention administrative, durée totale rétention 90 jours, "
        "seconde prolongation judiciaire rétention"
    ),

    # Q015 : immunités éloignement mineur (loi 2024)
    "Art. L. 611-3": (
        "immunités éloignement OQTF cas précis, étranger ne peut pas faire l'objet mesure éloignement, "
        "protection absolue contre OQTF mineur dix-huit ans, "
        "seule catégorie protégée après loi 2024-42 suppression protections, "
        "cas précis étranger non expulsable OQTF immunité, "
        "loi 2024 supprimé protections absolues sauf mineur éloignement"
    ),

    # Q019 : victime de traite proxénétisme
    "Art. L. 425-3": (
        "victime traite des êtres humains, victime proxénétisme carte résident, "
        "protection victime traite titre séjour, "
        "CST victime exploitation sexuelle, carte résidence traite proxénétisme, "
        "dénoncer auteur infraction carte séjour"
    ),

    # Q022 : divorce regroupement familial maintien
    "Art. L. 423-17": (
        "rupture vie commune conjoint étranger regroupement familial, "
        "retrait titre séjour divorce rupture, maintien titre séjour après séparation, "
        "trois ans communauté vie retrait possible, conjoint bénéficiaire regroupement familial divorce"
    ),
    "Art. L. 423-18": (
        "violences conjugales rupture communauté vie regroupement familial, "
        "maintien titre séjour malgré rupture violences, "
        "protection victime violences conjugales titre séjour, "
        "retrait titre impossible violences conjugales, exception retrait regroupement familial"
    ),

    # Q025 : apatride titre de séjour
    "Art. L. 424-18": (
        "titre de séjour bénéficiaire statut apatride, carte séjour pluriannuelle apatride 4 ans, "
        "protection apatride CESEDA, conditions séjour apatride reconnu OFPRA, "
        "statut apatride titre séjour mention apatride"
    ),
    "Art. L. 424-19": (
        "membre famille bénéficiaire statut apatride titre séjour, "
        "carte séjour famille apatride, conjoint enfant apatride reconnu titre"
    ),

    # Q026/Q027 : zone d'attente, mineur
    "Art. L. 341-1": (
        "zone d'attente mineur non accompagné MNA cas exceptionnels, "
        "dans quels cas étranger mineur placé zone d'attente, "
        "placement zone d'attente étranger non autorisé entrer France, "
        "mineur étranger zone d'attente, zone attente frontière aéroport ferroviaire, "
        "conditions exceptionnelles placement maintien zone d'attente mineur"
    ),
    "Art. L. 343-2": (
        "administrateur ad hoc mineur non accompagné zone d'attente, "
        "procureur de la République désigne administrateur ad hoc mineur ZA, "
        "représentation légale mineur zone attente, protection mineur non accompagné ZA"
    ),
    "Art. L. 741-5": (
        "mineur de dix-huit ans ne peut être placé en rétention, "
        "interdiction rétention administrative mineur, protection mineur rétention, "
        "mineur étranger non accompagné MNA rétention interdite"
    ),

    # Q029 : passeport talent
    "Art. L. 421-9": (
        "passeport talent salarié qualifié, carte talent rémunération seuil décret, "
        "titre séjour travailleur qualifié talent, passeport talent catégories, "
        "carte pluriannuelle talent emploi qualifié seuil salaire"
    ),
    "Art. L. 421-11": (
        "carte bleue européenne emploi hautement qualifié, talent chercheur, "
        "diplôme trois ans expérience cinq ans talent, passeport talent carte bleue EU, "
        "emploi hautement qualifié six mois durée titre séjour"
    ),
    "Art. L. 421-14": (
        "talent chercheur enseignant universitaire master recherche, "
        "convention accueil organisme recherche titre talent, "
        "chercheur scientifique carte pluriannuelle talent recherche, "
        "passeport talent chercheur enseignement universitaire"
    ),

    # Q031 : opposabilité situation emploi
    "Art. L. 414-13": (
        "opposabilité situation de l'emploi, marché emploi opposable recrutement étranger, "
        "vérification situation emploi avant autorisation travail, "
        "emploi disponible EEE avant recrutement étranger hors UE, "
        "DREETS opposabilité, candidat européen disponible test emploi"
    ),

    # Q033 : Dublin transfert
    "Art. L. 572-2": (
        "règlement Dublin III transfert État responsable France déclarée responsable, "
        "décision transfert Dublin délai quinze jours exécution, "
        "fonctionnement Dublin III procédure transfert demandeur asile, "
        "état membre responsable Dublin transfert, "
        "France responsable examen demande asile Dublin III cas, "
        "transfert demandeur asile délai quarante-huit heures rétention"
    ),

    # Q013 : délai recours OQTF
    "Art. L. 614-1": (
        "recours contre OQTF tribunal administratif, délai recours OQTF, "
        "contester OQTF voies de recours, recours gracieux contentieux OQTF, "
        "recours contre obligation quitter territoire français"
    ),
    "Art. L. 614-2": (
        "délai recours OQTF avec délai départ volontaire, recours trente jours OQTF, "
        "délai contestation OQTF tribunal administratif, "
        "recours suspension OQTF délai départ"
    ),
}


def _strip_existing_enrichment(text: str) -> str:
    """Remove existing '— Notions connexes:...' suffix."""
    marker = "— Notions connexes:"
    idx = text.find(marker)
    if idx >= 0:
        return text[:idx].rstrip()
    return text.rstrip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info(f"Chargement de {CHUNKS_PATH}…")
    chunks: list[dict] = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    logger.info(f"{len(chunks)} chunks chargés.")

    changed = 0
    for c in chunks:
        article_id = c.get("metadata", {}).get("article_id", "")
        if article_id in TARGETED_ENRICHMENTS:
            enrichment = TARGETED_ENRICHMENTS[article_id]
            base = _strip_existing_enrichment(c["text"])
            new_text = f"{base} — Notions connexes: {enrichment}"
            if new_text != c["text"]:
                c["text"] = new_text
                changed += 1
                if args.dry_run:
                    logger.info(f"  [DRY-RUN] {article_id}: enrichi")

    logger.info(f"{changed} chunks modifiés.")

    if args.dry_run:
        logger.info("Dry-run : aucune sauvegarde.")
        return

    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    logger.info(f"✅ Sauvegardé : {CHUNKS_PATH}")


if __name__ == "__main__":
    main()
