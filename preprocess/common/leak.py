"""Anti-fuite vers le test (T10 / A10) — chevauchement n-grammes vs FLORES-200 devtest.

Objectif (§4 T10) : **0** chevauchement entre une ligne d'entraînement et le jeu
d'évaluation. Sans ce contrôle, un BLEU élevé peut ne mesurer que de la mémorisation.

Référentiel attendu : `data/flores/devtest/` contenant des `.txt` ou `.jsonl`
(un champ texte par ligne ; `target`/`tgt`/`text` acceptés). Dossier vide/absent
→ `available` faux et l'étape est **sautée en le signalant** (jamais silencieusement).
"""
from __future__ import annotations

import json
from pathlib import Path


def _ngrams(text: str, n: int) -> set[str]:
    toks = text.split()
    if len(toks) < n:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}


class LeakChecker:
    def __init__(self, reference: str | Path | None, ngram: int = 8):
        self.ngram = ngram
        self.reference = Path(reference) if reference else None
        self._ref: set[str] = set()
        self.available = False
        if self.reference and self.reference.exists():
            self._load()

    def _load(self):
        files = sorted(p for p in self.reference.rglob("*")
                       if p.suffix.lower() in (".txt", ".jsonl"))
        for p in files:
            for line in p.read_text(encoding="utf-8").splitlines():
                text = line
                if p.suffix.lower() == ".jsonl":
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = rec.get("target") or rec.get("tgt") or rec.get("text") or ""
                self._ref |= _ngrams(text.strip(), self.ngram)
        self.available = bool(self._ref)

    def overlaps(self, text: str) -> bool:
        """Vrai si `text` partage au moins un n-gramme avec le référentiel d'éval."""
        if not self.available:
            return False
        return bool(_ngrams(text, self.ngram) & self._ref)
