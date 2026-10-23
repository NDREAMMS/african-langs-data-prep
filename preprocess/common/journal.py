"""Journal des rejets et calcul des rétentions (§3, §7).

Deux exigences du document :
  - principe §2.3 : chaque ligne écartée est journalisée avec
    `row_id, etape, raison, valeur_observee, langue, source, locuteur` ;
  - §7 : rapports de rétention par vocabulaire unique, tokens, locuteurs, source, domaine
    (un filtre qui vide un locuteur ou une source entière doit sauter aux yeux).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator


@dataclass
class Row:
    """Une unité de données entrant dans la chaîne."""

    row_id: str
    lang: str
    source: str
    speaker: str = ""
    domain: str = ""
    text: str = ""
    payload: dict = field(default_factory=dict)


class Journal:
    """Comptabilise entrées, rejets et rétentions pour un stage donné."""

    def __init__(self, stage: str, lang: str):
        self.stage = stage
        self.lang = lang
        self.read = 0
        self.kept = 0
        self.drops: Counter[str] = Counter()
        self.rejects: list[dict] = []
        # inventaire d'entrée pour les rétentions
        self._in_tokens = 0
        self._in_vocab: set[str] = set()
        self._in_speakers: set[str] = set()
        self._in_sources: Counter[str] = Counter()
        self._in_domains: Counter[str] = Counter()
        # inventaire de sortie
        self._out_tokens = 0
        self._out_vocab: set[str] = set()
        self._out_speakers: set[str] = set()
        self._out_sources: Counter[str] = Counter()
        self._out_domains: Counter[str] = Counter()

    # -- entrée -------------------------------------------------------------
    def see_input(self, row: Row, tokens: Iterable[str] = ()):
        self.read += 1
        toks = list(tokens)
        self._in_tokens += len(toks)
        self._in_vocab.update(toks)
        if row.speaker:
            self._in_speakers.add(row.speaker)
        if row.source:
            self._in_sources[row.source] += 1
        if row.domain:
            self._in_domains[row.domain] += 1

    def see_output(self, row: Row, tokens: Iterable[str] = ()):
        self.kept += 1
        toks = list(tokens)
        self._out_tokens += len(toks)
        self._out_vocab.update(toks)
        if row.speaker:
            self._out_speakers.add(row.speaker)
        if row.source:
            self._out_sources[row.source] += 1
        if row.domain:
            self._out_domains[row.domain] += 1

    # -- rejet --------------------------------------------------------------
    def drop(self, row: Row, etape: str, raison: str, valeur=None):
        self.drops[etape] += 1
        self.rejects.append({
            "row_id": row.row_id,
            "etape": etape,
            "raison": raison,
            "valeur_observee": valeur,
            "langue": row.lang,
            "source": row.source,
            "locuteur": row.speaker,
        })

    def drop_frac(self, etape: str) -> float:
        """Part du volume restant rejetée par une étape (§7, règle des 50 %)."""
        remaining = self.read - sum(v for k, v in self.drops.items() if k != etape)
        return self.drops[etape] / remaining if remaining else 0.0

    # -- rétention ----------------------------------------------------------
    def retention(self) -> dict:
        def frac(a, b):
            return round(a / b, 4) if b else None

        wiped = sorted(self._in_speakers - self._out_speakers)
        by_source = {
            s: frac(self._out_sources.get(s, 0), n)
            for s, n in self._in_sources.items()
        }
        by_domain = {
            d: frac(self._out_domains.get(d, 0), n)
            for d, n in self._in_domains.items()
        }
        return {
            "vocab_unique": frac(len(self._out_vocab), len(self._in_vocab)),
            "tokens": frac(self._out_tokens, self._in_tokens),
            "speakers": {
                "total": len(self._in_speakers),
                "kept": len(self._out_speakers),
                "wiped": wiped,
            },
            "by_source": by_source,
            "by_domain": by_domain,
        }

    # -- sorties ------------------------------------------------------------
    def write_rejects(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for r in self.rejects:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def report(self) -> dict:
        return {
            "lang": self.lang,
            "stage": self.stage,
            "read": self.read,
            "kept": self.kept,
            "drops": dict(self.drops),
            "retention": self.retention(),
        }


def run_stages(rows: Iterable[Row], stages: list[tuple[str, Callable]]) -> Iterator[Row]:
    """Exécute des stages séquentiels labellisés : (nom, fn(row)->Row|None).

    Un stage renvoie la Row (éventuellement modifiée) ou None pour rejeter.
    Le rejet doit déjà avoir été journalisé par le stage (accès au Journal via closure).
    """
    for row in rows:
        cur = row
        for _name, fn in stages:
            cur = fn(cur)
            if cur is None:
                break
        if cur is not None:
            yield cur
