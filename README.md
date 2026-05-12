# Multi RAG Bot

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-local--first-orange)

Assistant RAG multi-domaines oriente documents juridiques. Le projet permet d'ingester des documents par domaine, de les decouper avec une strategie de chunking adaptee, de generer des embeddings, puis de stocker les chunks dans Qdrant pour la recherche semantique.

Aujourd'hui, la premiere verticale en place est `droit_etranger`, avec un pipeline local complet :

- chargement du document source
- chunking specialise
- generation optionnelle des embeddings OpenAI
- indexation optionnelle dans Qdrant
- retrieval minimal pour reconstruire un prompt RAG

## Idee

L'objectif n'est pas d'avoir un seul RAG monolithique, mais plusieurs domaines juridiques ou metiers, chacun avec :

- ses documents
- ses regles de chunking
- son prompt metier
- ses synonymes
- sa ou ses collections vectorielles

La structure actuelle est donc pensee pour du `multi-domain ready`

## Structure

```text
domains/
  droit_etranger/
    documents.yaml
    chunker_config.yaml
    prompt_template.txt
    synonyms.txt

rag-plateform/
  pipeline.py
  ingestion/
    loaders/
    chunkers/
    embedders/
  retrieval/
    vector_store.py
    retriever.py

api/
  main.py
  app.py
  dependencies.py
  routes/
    health.py
    ask.py
    ingest.py

scripts/
  ingest.py
  retrieve.py
  web_ui.py
  serve_webapp.py

webapp/
  index.html
  login/
  docs/
  chat/
  assets/
```

## Principe

1. Le pipeline charge les documents declares dans `domains/<domain>/documents.yaml`.
2. Chaque document est traite par un loader adapte, par exemple `pdf_url` ou `pdf_local`.
3. Le contenu est decoupe en chunks via un chunker specialise.
4. Les chunks sont sauvegardes en `jsonl` dans `data/chunks/`.
5. Si OpenAI et Qdrant sont configures, les chunks sont vectorises puis indexes.
6. Le retriever reconstruit ensuite un contexte RAG a partir des meilleurs hits.

## Initialisation

### 1. Creer le fichier `.env`

```bash
cp .env.example .env
```

Renseigne ensuite les variables utiles :

```env
OPENAI_API_KEY=
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small
RESPONSE_MODEL=gpt-4.1-mini
EMBEDDING_BATCH_SIZE=32
FORCE_REDOWNLOAD=false
```

### 2. Installer l'environnement Python

Le projet utilise maintenant `pyproject.toml` comme source principale de dependances.

```bash
python -m venv .venv
```

Sous Linux / macOS :

```bash
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Sous Windows PowerShell :

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
```

`requirements.txt` reste present pour compatibilite, mais `pyproject.toml` est maintenant la source de verite.

## Ingestion

Commande principale :

```bash
python main.py --domain droit_etranger
```

Commande equivalente :

```bash
python scripts/ingest.py --domain droit_etranger
```

Resultats attendus :

- le PDF source est telecharge ou reutilise depuis `data/raw/`
- les chunks sont ecrits dans `data/chunks/<doc_id>.jsonl`
- si OpenAI et Qdrant sont configures, les chunks sont indexes dans la collection declaree dans `documents.yaml`

## Retrieval

Pour tester la recherche apres ingestion :

```bash
python scripts/retrieve.py --domain droit_etranger --question "Quelles sont les regles de sejour ?" --limit 5
```

Le script affiche :

- les meilleurs hits Qdrant
- les articles retrouves
- le prompt final construit avec `domains/<domain>/prompt_template.txt`

## UI locale

Une interface web minimale est disponible pour poser une question depuis le navigateur :

```bash
python scripts/web_ui.py --host 127.0.0.1 --port 8000
```

Puis ouvre `http://127.0.0.1:8000`.

La page permet de :

- choisir le domaine
- saisir une question
- lancer le retrieval
- generer une reponse a partir du prompt RAG
- voir les hits retournes et le prompt RAG genere

## API backend

Une entree backend FastAPI dediee est maintenant disponible, separee du CLI et de l'UI locale :

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload
```

Points utiles au demarrage :

- `http://127.0.0.1:8001/health` pour verifier que l'app repond
- `http://127.0.0.1:8001/docs` pour consulter le contrat OpenAPI genere

La structure `api/` est prete a accueillir les routes `health`, `ask` et `ingest` sans brancher directement la future webapp sur l'UI locale.

## Webapp shell

Une webapp statique minimale est disponible pour avancer cote front sans attendre les routes metier finales.

1. Demarre l'API :

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload
```

2. Demarre la webapp :

```bash
python scripts/serve_webapp.py --host 127.0.0.1 --port 4173
```

3. Ouvre :

```text
http://127.0.0.1:4173
```

Le shell front :

- appelle `GET /health`
- expose des routes/pieces pretes pour `login`, `docs` et `chat`
- reste separe de l'API, tout en pointant vers `http://127.0.0.1:8001` par defaut

Tu peux changer la cible API dans `webapp/assets/config.js`.

## Domaine actif

Le domaine actuellement configure est :

- `droit_etranger`

Il contient deja :

- un document source CESEDA
- un chunker specialise par article
- un prompt metier
- un fichier de synonymes pour la suite du retrieval

## Tests

Lancer les tests unitaires :

```bash
python -m unittest discover -s tests -v
```

Ils couvrent :

- le loader PDF local
- la reutilisation du cache pour le loader PDF distant
- le pipeline d'ingestion avec faux embedder et faux vector store
- la construction du prompt et des identifiants Qdrant



## Etat actuel

Ce qui est pret :

- pipeline local `load -> chunk`
- embeddings OpenAI
- stockage Qdrant
- retrieval minimal
- structure par domaine

Ce qui reste a faire ensuite :

- routage entre plusieurs domaines
- plusieurs strategies de retrieval selon le type de domaine
- synthese cross-domain
- interface web ou API applicative
- observabilite et industrialisation cloud
