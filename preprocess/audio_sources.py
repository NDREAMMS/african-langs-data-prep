"""Lecteurs des sources audio Lingala.

Deux sources vérifiées sur le disque :
  - BibleTTS  : data/bibletts/extracted/lingala/<split>/<BOOK>/<..>.flac (+ .txt), 48 kHz studio.
  - WAXAL ASR : data/waxal/asr/lin/<split>/*.parquet, audio (mp3) + transcrip./speaker_id, 16 kHz.

Le champ `source` (§5 A11) distingue ces deux mondes : BibleTTS=48k bande pleine,
WAXAL=16k bande 8-12 kHz vide. Ne jamais les mélanger sans ce marqueur.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .common.journal import Row


@dataclass
class AudioItem:
    row: Row
    samples: np.ndarray   # float32 mono
    sr: int
    path: str = ""
    payload_bytes: bytes | None = None


def _read_flac_mono(path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)  # mono
    return mono.astype(np.float32), sr


def iter_bibletts(root: str | Path, lang: str = "lin", splits: tuple[str, ...] = ("dev",)):
    """Itère les couples .flac/.txt de BibleTTS.

    `root` pointe vers le dossier contenant `lingala/` (ex. data/bibletts/extracted).
    domain = bible (registre étroit, §7) ; source = bibletts.
    """
    root = Path(root)
    base = root / "lingala"
    if not base.exists():
        base = root  # root est déjà le dossier lingala
    for split in splits:
        sdir = base / split
        if not sdir.exists():
            continue
        for flac in sorted(sdir.rglob("*.flac")):
            txt = flac.with_suffix(".txt")
            if not txt.exists():
                continue
            book = flac.parent.name
            item_id = f"bibletts_{split}_{flac.stem}"
            row = Row(
                row_id=item_id,
                lang=lang,
                source="bibletts",
                speaker=f"bibletts_{book}",   # 1 narrateur par livre (D14)
                domain="bible",
                text=txt.read_text(encoding="utf-8").strip(),
                payload={"split": split, "book": book, "path": str(flac)},
            )
            yield AudioItem(row=row, samples=np.empty(0, np.float32), sr=0, path=str(flac))


def iter_waxal(root: str | Path, split: str = "train", lang: str = "lin",
               limit: int | None = None):
    """Itère les enregistrements WAXAL (audio embarqué dans le parquet).

    `limit` borne le nombre d'items produits (évite de charger tout le parquet
    quand on ne veut qu'un échantillon).
    """
    import pyarrow.parquet as pq

    root = Path(root)
    produced = 0
    for parquet in sorted((root / split).glob("*.parquet")):
        table = pq.read_table(parquet)
        for r in table.to_pylist():
            if limit is not None and produced >= limit:
                return
            row = Row(
                row_id=f"waxal_{split}_{r['id']}",
                lang=lang,
                source="waxal",
                speaker=str(r["speaker_id"]),
                domain="waxal_read",           # registre lecture (à préciser §7)
                text=(r.get("transcription") or "").strip(),
                payload={"gender": r.get("gender"), "path": r["audio"]["path"]},
            )
            produced += 1
            yield AudioItem(row=row, samples=np.empty(0, np.float32), sr=0,
                            path=r["audio"]["path"], payload_bytes=r["audio"]["bytes"])


def load_audio(item: AudioItem) -> AudioItem:
    """A1 — chargement paresseux (BibleTTS depuis .flac, WAXAL depuis les octets)."""
    if item.row.source == "bibletts":
        item.samples, item.sr = _read_flac_mono(Path(item.path))
    elif item.row.source == "waxal":
        import soundfile as sf

        data, sr = sf.read(io.BytesIO(item.payload_bytes), dtype="float32", always_2d=True)
        item.samples, item.sr = data.mean(axis=1).astype(np.float32), sr
    else:
        item.samples, item.sr = _read_flac_mono(Path(item.path))
    return item
