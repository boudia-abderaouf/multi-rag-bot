# multi-rag-bot

RAG platform for French legal text, currently focused on **droit des étrangers (CESEDA)**.

## Stack

- **Vector DB**: Qdrant (`http://localhost:6333` by default)
- **Embeddings**: OpenAI `text-embedding-3-small`
- **Generation / HyDE / query expansion**: OpenAI `gpt-4.1-mini`
- **Config**: `.env` file at project root (see `config/settings.py` for all keys)

## Architecture

```
domains/<domain>/          ← config par domaine (documents, chunker, prompt, benchmark)
rag-plateform/
  ingestion/               ← loaders (PDF, HTML) + chunkers + embedders
  retrieval/
    retriever.py           ← multi-query RRF + HyDE + direct guarantee
    reranker.py            ← score (preserve RRF order) ou cross_encoder
    vector_store.py        ← client Qdrant
  generation/
    openai_responder.py
  pipeline.py              ← ingestion orchestration
scripts/
  ingest.py                ← ingestion d'un domaine
  run_benchmark.py         ← lance le pipeline complet sur le benchmark YAML
  score_benchmark.py       ← calcule recall/precision/MRR sur un fichier JSONL
  enrich_chunks.py         ← enrichissement des métadonnées de chunks existants
  reingest_clean.py        ← ré-ingestion propre (supprime + réindexe)
data/benchmark/<domain>/   ← résultats des runs (JSONL horodatés)
```

## Commandes clés

```bash
# Ingestion
python scripts/ingest.py --domain droit_etranger

# Benchmark complet (retrieval + génération LLM)
python scripts/run_benchmark.py --domain droit_etranger

# Benchmark dry-run (retrieval uniquement, sans appel LLM)
python scripts/run_benchmark.py --domain droit_etranger --dry-run

# Benchmark avec reranker
python scripts/run_benchmark.py --domain droit_etranger --rerank-top-k 20
python scripts/run_benchmark.py --domain droit_etranger --rerank-top-k 20 --rerank-backend cross_encoder

# Scorer un run
python scripts/score_benchmark.py data/benchmark/droit_etranger/<fichier>.jsonl

# Tests
python -m pytest tests/ -v
```

## Pipeline retrieval — invariants critiques

1. **Ne jamais re-trier les résultats RRF par score cosinus.**
   `retrieve_for_domain()` retourne `[RRF results] + [extras directs]`. Les extras ont des scores cosinus (0.4–0.9) bien supérieurs aux scores RRF (0.001–0.05). Re-trier par score ferait remonter tous les extras et détruirait le consensus multi-requêtes.

2. **`reranker.backend="score"` = préserver l'ordre RRF**, pas trier. C'est intentionnel — ne pas le "corriger".

3. **Le benchmark est la seule source de vérité** pour valider tout changement au retrieval ou au reranker. Toujours scorer avant/après.

4. **`data/`** contient les données brutes et les résultats benchmark — ne pas supprimer ou modifier sans confirmation explicite.

## Seuil de qualité

`recall@k >= 80%` ET `precision@k >= 80%` (calculés sur `generation_chunks` quand le reranker est actif, sinon sur `retrieved_chunks`).

## Imports dans les scripts

Les scripts ajoutent `rag-plateform/` au `sys.path`, donc les imports s'écrivent :
```python
from retrieval.retriever import Retriever   # pas rag-plateform.retrieval
from generation.openai_responder import OpenAIResponder
```
