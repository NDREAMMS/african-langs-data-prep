"""Configuration de la chaîne corpus (§2.2 transposé) : aucun seuil en dur.

Le corpus est un Actif *amont* : il produit le JSONL
`{src,tgt,lang_src,lang_tgt,domain}` que consomme `ml.preprocess.run nmt`.
On y applique le même principe qu'au prétraitement — un seuil de filtrage
n'existe qu'après calibrage (`provenance: calibrage_<lang>_<date>`) ; sinon le
corpus est marqué `publishable: false` et la publication est bloquée.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

PKG_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PKG_ROOT / "configs"

# Seuils chiffrés dont la `provenance` doit valoir calibrage_* pour être validés.
CALIBRABLE = ("C4_length", "C5_ratio", "C7_alphabet", "C8_dedup")


@dataclass
class CorpusConfig:
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

    def provenance(self, block: str):
        return (self.raw.get("text", {}).get(block) or {}).get("provenance")

    def uncalibrated(self) -> list[str]:
        out = []
        for block in CALIBRABLE:
            prov = self.provenance(block)
            if prov is None or not str(prov).startswith("calibrage_"):
                out.append(f"text.{block}")
        return out

    @property
    def publishable(self) -> bool:
        return not self.uncalibrated()

    # -- politique de licence (D6) -----------------------------------------
    def license_ok(self, lic: str | None) -> bool:
        """Vrai si la licence est permissive (production commerciale possible)."""
        if not lic:
            return False
        allowed = self.raw.get("licence", {}).get("permises", [])
        low = lic.lower()
        return any(a.lower() in low for a in allowed)


def load_corpus_config(path: str | Path | None = None) -> CorpusConfig:
    path = Path(path) if path else CONFIG_DIR / "corpus.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False,
                           default=str).encode("utf-8")
    h = hashlib.sha256(canonical).hexdigest()[:12]
    return CorpusConfig(raw=raw, path=path, hash=h)
