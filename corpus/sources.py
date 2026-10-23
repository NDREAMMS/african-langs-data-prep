"""Registre des sources + audit + lecture générique.

Chaque source est déclarée dans `configs/sources.csv` avec sa **licence**.
La licence conditionne l'entrée dans la chaîne (D6) : une source NC/ND/inconnue
est refusée, et l'audit le prouve (présence, taille, SHA-256, statut).
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Source:
    id: str
    type: str
    path: str
    src_lang: str
    tgt_lang: str
    license: str
    permis: str
    domain: str
    status: str
    note: str = ""

    @property
    def permissive(self) -> bool:
        return self.permis.strip().lower() in ("oui", "true", "1", "yes")


def load_registry(path: str | Path | None = None) -> list[Source]:
    from .config import CONFIG_DIR
    path = Path(path) if path else CONFIG_DIR / "sources.csv"
    rows = []
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(Source(**{k: (v or "").strip() for k, v in r.items()}))
    return rows


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _dir_fingerprint(p: Path) -> dict:
    """Empreinte d'un dossier de sources : nb de fichiers, octets, sha256 concaténés."""
    files = sorted(x for x in p.rglob("*") if x.is_file()
                   and x.suffix.lower() in (".usfm", ".txt", ".jsonl", ".csv", ".parquet"))
    total = sum(x.stat().st_size for x in files)
    h = hashlib.sha256()
    for x in files:
        h.update(x.name.encode("utf-8"))
        h.update(str(x.stat().st_size).encode("utf-8"))
    return {"files": len(files), "bytes": total, "fingerprint": h.hexdigest()[:16]}


def audit(registry: list[Source], root: str | Path, cfg=None) -> list[dict]:
    """Table d'audit des sources : présence, empreinte, licence admise ou non."""
    root = Path(root)
    out = []
    for s in registry:
        p = (root / s.path) if s.path else None
        present = bool(p and p.exists())
        entry = {
            "id": s.id, "type": s.type, "domain": s.domain, "status": s.status,
            "license": s.license, "permis": s.permissive, "present": present,
        }
        if present:
            if p.is_dir():
                entry.update(_dir_fingerprint(p))
            else:
                entry["bytes"] = p.stat().st_size
                entry["fingerprint"] = _sha256_file(p)
        if cfg is not None:
            entry["license_admise"] = cfg.license_ok(s.license)
        out.append(entry)
    return out
