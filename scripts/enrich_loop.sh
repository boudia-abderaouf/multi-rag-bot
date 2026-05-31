#!/usr/bin/env bash
# Lance enrich_chunks.py en boucle jusqu'à ce que tous les chunks soient enrichis.
set -e
cd /Users/aitkettoutyounes/Desktop/Perso/multi-rag-bot

while true; do
    TOTAL=$(wc -l < data/chunks/ceseda.jsonl | tr -d ' ')
    DONE=$(grep -c "Notions connexes" data/chunks/ceseda.jsonl || true)
    echo "[$(date '+%H:%M:%S')] $DONE/$TOTAL chunks enrichis"

    if [ "$DONE" -ge "$TOTAL" ]; then
        echo "[$(date '+%H:%M:%S')] ✅ Tous les chunks sont enrichis. Fin."
        break
    fi

    echo "[$(date '+%H:%M:%S')] Lancement enrich_chunks.py…"
    python3 scripts/enrich_chunks.py --embed-batch 32 || true
    echo "[$(date '+%H:%M:%S')] Processus terminé (ou interrompu). Reprise dans 5s…"
    sleep 5
done
