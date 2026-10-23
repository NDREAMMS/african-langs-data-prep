"""Qualité de parallélisme (T9) — SONAR / LaBSE, chargement paresseux.

Le seuil de cosinus ne vaut **que** pour la paire de langues sur laquelle il a été
calibré (§3.4, « à calibrer PAR PAIRE »). Ce module fournit le scoring ; le seuil
reste dans la config, avec sa provenance.

Aucune dépendance n'est obligatoire : si `sentence-transformers` ou le modèle ne sont
pas fournis, `available` est faux et l'étape est **sautée en le signalant** — jamais
silencieusement (§2.2).
"""
from __future__ import annotations

from pathlib import Path


class ParallelScorer:
    def __init__(self, tool: str = "sonar", model_path: str | None = None):
        self.tool = tool
        self.available = False
        self._model = None
        if model_path:
            try:
                from sentence_transformers import SentenceTransformer  # import paresseux

                self._model = SentenceTransformer(model_path)
                self.available = True
            except Exception:
                self.available = False

    def cosine(self, src: str, tgt: str) -> float | None:
        """Cosinus entre les plongements des deux côtés, ou None si indisponible."""
        if not self.available:
            return None
        import numpy as np

        emb = self._model.encode([src, tgt], normalize_embeddings=True)
        return float(np.dot(emb[0], emb[1]))
