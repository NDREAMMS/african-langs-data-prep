"""Identification de langue (T6) — avec garde-fou de couverture (§3.4).

Le document avertit explicitement : `fasttext lid.176` est **absent ou sous-représenté**
sur nos langues (wo/lin/bam). Le seuil ne vaut donc rien tant qu'on n'a pas vérifié
le rappel réel. Ce module :
  - utilise fasttext si le modèle est fourni,
  - sinon bascule sur un classifieur « alphabet » (repli), en le signalant,
  - expose le nom de la méthode réellement employée pour la traçabilité.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Codes fasttext -> nos codes internes (à compléter après vérification §3.4).
LID_TO_INTERNAL = {"ln": "lin", "fr": "fra", "wo": "wol", "bm": "bam"}


@dataclass
class LangIdResult:
    label: str
    confidence: float
    method: str


class LangId:
    def __init__(self, model_path: str | None = None):
        self.method = "none"
        self._model = None
        if model_path and Path(model_path).exists():
            import fasttext  # import paresseux

            self._model = fasttext.load_model(model_path)
            self.method = "fasttext_lid176"

    def predict(self, text: str) -> LangIdResult:
        if self._model is not None:
            labels, probs = self._model.predict(text.replace("\n", " "), k=1)
            raw = labels[0].replace("__label__", "")
            return LangIdResult(LID_TO_INTERNAL.get(raw, raw), float(probs[0]), self.method)
        # Repli non-supervisé : signalé comme tel, jamais présenté comme fasttext.
        return LangIdResult("unknown", 0.0, "unavailable")
