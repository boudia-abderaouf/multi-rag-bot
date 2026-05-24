"""
Reranker — sélectionne les K chunks les plus pertinents parmi les résultats du retriever.

Deux backends disponibles :
  - "score"        : tri par score RRF existant, 0 coût supplémentaire (défaut)
  - "cross_encoder": cross-encoder multilingue via sentence-transformers
                     (plus précis, ~100-300 ms pour 400 chunks, 0 coût API)

Usage typique :
    reranker = Reranker()                          # backend score, gratuit
    reranker = Reranker(backend="cross_encoder")   # cross-encoder multilingue

    hits_all   = retriever.retrieve_for_domain(...)  # ~400-500 chunks
    hits_top20 = reranker.rerank(query, hits_all, top_k=20)
    prompt     = retriever.build_prompt(hits=hits_top20, ...)
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Modèle multilingue léger (~85 MB) — supporte le français
_DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class Reranker:
    """Re-classe les chunks récupérés pour ne garder que les plus pertinents."""

    def __init__(
        self,
        backend: str = "score",
        model_name: str | None = None,
    ):
        """
        Args:
            backend    : "score" (défaut, gratuit) ou "cross_encoder"
            model_name : nom du modèle HuggingFace (cross_encoder uniquement)
        """
        if backend not in ("score", "cross_encoder"):
            raise ValueError(f"backend doit être 'score' ou 'cross_encoder', reçu: {backend!r}")

        self.backend = backend
        self._model: Any = None

        if backend == "cross_encoder":
            self._load_cross_encoder(model_name or _DEFAULT_CROSS_ENCODER_MODEL)

    # ── Chargement du modèle ─────────────────────────────────────────────────

    def _load_cross_encoder(self, model_name: str) -> None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Chargement du cross-encoder : {model_name}")
            self._model = CrossEncoder(model_name)
            logger.info("Cross-encoder prêt.")
        except ImportError:
            logger.warning(
                "sentence-transformers non installé — fallback sur backend 'score'. "
                "Installez-le avec : pip install sentence-transformers"
            )
            self.backend = "score"
        except Exception as exc:
            logger.warning(f"Impossible de charger le cross-encoder ({exc}) — fallback 'score'.")
            self.backend = "score"

    # ── API publique ─────────────────────────────────────────────────────────

    def rerank(self, query: str, hits: list, top_k: int = 20) -> list:
        """Retourne les `top_k` chunks les plus pertinents pour `query`.

        Args:
            query  : question originale de l'utilisateur
            hits   : liste de SearchHit (résultats du retriever)
            top_k  : nombre de chunks à conserver pour la génération

        Returns:
            Sous-liste triée par pertinence décroissante, taille ≤ top_k
        """
        if not hits:
            return []

        top_k = min(top_k, len(hits))

        if self.backend == "cross_encoder" and self._model is not None:
            return self._rerank_cross_encoder(query, hits, top_k)

        return self._rerank_score(hits, top_k)

    # ── Backends ─────────────────────────────────────────────────────────────

    def _rerank_score(self, hits: list, top_k: int) -> list:
        """Tri simple par score décroissant (RRF ou cosinus).

        Avantages : 0 coût, 0 latence supplémentaire.
        Limite    : le score RRF reflète la consensus inter-requêtes mais pas
                    la pertinence fine par rapport à la question exacte.
        """
        return sorted(hits, key=lambda h: h.score, reverse=True)[:top_k]

    def _rerank_cross_encoder(self, query: str, hits: list, top_k: int) -> list:
        """Score chaque chunk avec un cross-encoder (question, chunk) → pertinence.

        Plus précis que le score RRF car le modèle voit la paire complète.
        Latence : ~100-300 ms pour 400 chunks sur CPU.
        """
        texts = [h.payload.get("text", "") for h in hits]
        pairs = [(query, text) for text in texts]

        try:
            scores = self._model.predict(pairs, show_progress_bar=False)
        except Exception as exc:
            logger.warning(f"Cross-encoder predict() échoué ({exc}) — fallback score.")
            return self._rerank_score(hits, top_k)

        ranked = sorted(zip(scores, hits), key=lambda x: float(x[0]), reverse=True)
        return [h for _, h in ranked[:top_k]]

    # ── Helpers ──────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config: dict) -> "Reranker":
        """Construit un Reranker depuis un dict de config.

        Exemple :
            {"backend": "cross_encoder", "top_k": 20}
        """
        return cls(
            backend=config.get("backend", "score"),
            model_name=config.get("model_name"),
        )
