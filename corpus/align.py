"""Alignement verset par verset (FR ↔ lin) et sérialisation JSONL.

Deux entrées acceptées :
  - deux dossiers USFM (eBible `fraLSG` + eBible `lin`) ;
  - un dossier BibleTTS (noms `LIVRE_CCC_Verse_VVV.txt`) + le dossier USFM français.

La clé d'alignement est (livre, chapitre, verset) : un appariement *exact*.
Les versets présents d'un seul côté sont **rapportés** (jamais silencieusement
perdus) — c'est là que se lisent les écarts de versification.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .usfm import book_name, load_dir

BIBLETTS = re.compile(r"^(?P<book>[1-3]?[A-Z]{2,3})_(?P<ch>\d+)_Verse_(?P<v>\d+)\.txt$")


def load_bibletts_text(root: str | Path) -> dict[tuple[str, int, int], str]:
    out: dict[tuple[str, int, int], str] = {}
    for p in sorted(Path(root).rglob("*.txt")):
        m = BIBLETTS.match(p.name)
        if not m:
            continue
        out[(m["book"], int(m["ch"]), int(m["v"]))] = p.read_text(
            encoding="utf-8-sig").strip()
    return out


def align(src: dict, tgt: dict) -> tuple[list[tuple[tuple, str, str]], dict]:
    """Apparie deux index verset → (paires, rapport des écarts)."""
    both = sorted(set(src) & set(tgt))
    pairs = [(k, src[k], tgt[k]) for k in both]
    report = {
        "aligned": len(pairs),
        "src_only": sorted(".".join(map(str, k)) for k in set(src) - set(tgt)),
        "tgt_only": sorted(".".join(map(str, k)) for k in set(tgt) - set(src)),
    }
    return pairs, report


def write_jsonl(pairs, path: str | Path, *, lang_src: str, lang_tgt: str,
                domain: str, source: str, license: str):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for (book, ch, v), s, t in pairs:
            fh.write(json.dumps({
                "row_id": f"{book}.{ch}.{v}",
                "src": s, "tgt": t,
                "lang_src": lang_src, "lang_tgt": lang_tgt,
                "domain": domain, "source": source, "license": license,
                "ref": f"{book_name(book)} {ch}:{v}", "book": book,
            }, ensure_ascii=False) + "\n")


def build_bible(src_dir: str | Path, tgt_dir: str | Path, out_path: str | Path,
                *, lang_src: str = "fra", lang_tgt: str = "lin",
                domain: str = "bible", source: str = "ebible",
                license: str = "CC-BY-SA-4.0 + domaine public") -> dict:
    src = load_dir(src_dir)
    tgt = load_dir(tgt_dir)
    pairs, report = align(src, tgt)
    write_jsonl(pairs, out_path, lang_src=lang_src, lang_tgt=lang_tgt,
                domain=domain, source=source, license=license)
    report["written"] = str(out_path)
    return report
