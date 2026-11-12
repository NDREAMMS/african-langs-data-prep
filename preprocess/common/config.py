"""Chargement de preprocess.yaml : hash de version + garde-fou de calibrage.

Principes §2 du document de prétraitement :
  1. configuration unique, aucun seuil en dur ;
  2. un seuil n'existe qu'après calibrage — sinon le manifest est non publiable.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PKG_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PKG_ROOT / "configs"

# Clés de seuils réellement numériques : leur `provenance` doit valoir calibrage_*.
# Les règles structurelles (schema, normalisation) sont exemptées (provenance: null légitime).
CALIBRABLE = (
    "T4_length", "T5_length_ratio", "T6_langid", "T7_alphabet", "T8_minhash", "T9_parallel",
    "A5_duration", "A6_rate", "A7_dnsmos", "A8_snr", "A9_asr_wer", "A3_loudness",
)

VALIDATION_MODES = ("human", "auto")
DEFAULT_HYPOTHESIS_BLOCKS = ("T8_minhash", "A3_loudness")


@dataclass
class Config:
    raw: dict
    path: Path
    hash: str

    def get(self, dotted: str, default=None):
        node = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def lang(self) -> str:
        return self.raw["meta"]["lang"]

    def provenance(self, section: str, key: str):
        return self.raw.get(section, {}).get(key, {}).get("provenance")

    # -- politique de validation (décision « sans relecteur ») --------------
    def validation_mode(self) -> str:
        """`human` (annotation) ou `auto` (calibrage automatique + hypothèses)."""
        mode = str(self.get("validation.mode", "human")).lower()
        return mode if mode in VALIDATION_MODES else "human"

    def hypothesis_blocks(self) -> set[str]:
        blocks = self.get("validation.hypothesis_blocks")
        if blocks is None:
            return set(DEFAULT_HYPOTHESIS_BLOCKS)
        if isinstance(blocks, str):
            return {blocks}
        return set(blocks)

    def allow_hypothesis(self) -> bool:
        return bool(self.get("validation.allow_hypothesis", False))

    def _provenance_ok(self, block: str, prov) -> bool:
        if prov is None:
            return False
        prov = str(prov)
        if prov.startswith("calibrage_"):
            return True
        if self.validation_mode() == "auto":
            if prov.startswith("auto_"):
                return True
            if (self.allow_hypothesis() and block in self.hypothesis_blocks()
                    and prov.startswith("hypothese_")):
                return True
        return False

    def _block_provenance(self, block: str) -> str | None:
        section = "text" if block.startswith("T") else "audio"
        return (self.raw.get(section, {}).get(block) or {}).get("provenance")

    def blocked_blocks(self) -> list[str]:
        """Seuils sans provenance admise par le mode de validation courant."""
        return [f"{'text' if b.startswith('T') else 'audio'}.{b}"
                for b in CALIBRABLE
                if not self._provenance_ok(b, self._block_provenance(b))]

    def uncalibrated(self) -> list[str]:
        """Alias rétro-compatible de `blocked_blocks()` (ancien nom §2.2)."""
        return self.blocked_blocks()

    def status(self) -> str:
        """`blocked` | `auto` | `human` — niveau de validation effectif."""
        if self.blocked_blocks():
            return "blocked"
        provs = [str(self._block_provenance(b) or "") for b in CALIBRABLE]
        if any(p.startswith(("auto_", "hypothese_")) for p in provs):
            return "auto"
        return "human"

    @property
    def validation_level(self) -> str:
        return {
            "blocked": "blocked",
            "auto": "auto_unvalidated",
            "human": "human_validated",
        }[self.status()]

    @property
    def publishable(self) -> bool:
        """Un manifest est publiable dès que le mode de validation est satisfait.

        Les gates automatiques peuvent encore le rétrograder : voir `gates.evaluate`.
        """
        return self.status() != "blocked"


def load_config(path: str | Path | None = None) -> Config:
    path = Path(path) if path else CONFIG_DIR / "preprocess.yaml"
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    # Hash canonique du contenu sémantique (ignore les commentaires).
    canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
    h = hashlib.sha256(canonical).hexdigest()[:12]
    return Config(raw=raw, path=path, hash=h)


def load_numerals(path: str | Path | None = None, lang: str | None = None) -> dict | None:
    """Table de numéraux. `lang` cherche `numerals_<lang>.yaml` ; None si absente.

    §4 T3 : chaque langue porte SA table (FR côté src, cible côté tgt) — pas de table
    unique appliquée indifféremment aux deux.
    """
    if path is None and lang is not None:
        path = CONFIG_DIR / f"numerals_{lang}.yaml"
        if not Path(path).exists():
            return None
    path = Path(path) if path else CONFIG_DIR / "numerals_lin.yaml"
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


@dataclass
class ManifestMeta:
    """Provenance attachée à un manifest produit."""

    lang: str
    stage: str
    run_id: str
    cfg_hash: str
    publishable: bool
    uncalibrated: list[str] = field(default_factory=list)
