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

    def uncalibrated(self) -> list[str]:
        """Liste des seuils calibrables encore sans provenance `calibrage_*`.

        Un seuil est valide s'il porte `provenance: calibrage_<lang>_<date>`.
        `provenance: null` = jamais calibré ; toute autre valeur = provenance invalide.
        """
        out = []
        for block in CALIBRABLE:
            section = "text" if block.startswith("T") else "audio"
            prov = (self.raw.get(section, {}).get(block) or {}).get("provenance")
            if prov is None or not str(prov).startswith("calibrage_"):
                out.append(f"{section}.{block}")
        return out

    @property
    def publishable(self) -> bool:
        return not self.uncalibrated()


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
