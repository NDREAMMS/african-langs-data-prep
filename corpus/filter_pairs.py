"""Normalisation, filtrage, dédoublonnage, découpage du corpus.

Trois catégories de sortie (§2 de la note v1.2) :
  - **accepté**   → `manifest_corpus.jsonl` (alimente le stage `nmt`) ;
  - **quarantaine** → `quarantine.jsonl` : signal suspect mais pas de preuve (bande grise) ;
  - **rejeté**    → `rejects.jsonl` (preuve d'erreur ou doublon).

La quarantaine sert à une **validation humaine ultérieure** : on ne jette pas une
paire dont on n'est pas sûr, on la met de côté. Aucun seuil n'est en dur : tout
vient de `configs/corpus.yaml` (`min`/`max` = bornes dures, `warn_*` = bande grise).
"""
from __future__ import annotations

import json
from pathlib import Path

from ml.preprocess.common import unicode_norm as U
from ml.preprocess.common.dedup import MinHashDedup, exact_key, stable_hash
from ml.preprocess.common.journal import Journal, Row
from ml.preprocess.text_nmt import LINGALA_ALPHABET

_TWO64 = float(1 << 64)


def _alpha_ratio(text: str, allowed: set[str]) -> float:
    letters = [c.lower() for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(c in allowed for c in letters) / len(letters)


def _band(value: float, hard_min, hard_max, warn_min, warn_max) -> str | None:
    """None si conforme, "reject" hors bornes dures, "warn" dans la bande grise."""
    if hard_min is not None and value < hard_min:
        return "reject"
    if hard_max is not None and value > hard_max:
        return "reject"
    if warn_min is not None and value < warn_min:
        return "warn"
    if warn_max is not None and value > warn_max:
        return "warn"
    return None


def split_of(value: str, dev: float, test: float) -> str:
    """Découpage déterministe par hash stable (T11 transposé)."""
    h = stable_hash(value, salt="corpus") / _TWO64
    return "test" if h < test else "dev" if h < test + dev else "train"


def run(cfg, input_path: str | Path, out_dir: str | Path, limit: int | None = None) -> Journal:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    c4 = cfg.get("text.C4_length") or {}
    c5 = cfg.get("text.C5_ratio") or {}
    c7 = cfg.get("text.C7_alphabet") or {}
    dev = float(cfg.get("split.dev", 0.05))
    test = float(cfg.get("split.test", 0.05))
    book_aware = cfg.get("split.method", "book_aware") == "book_aware"

    dedup = MinHashDedup(ngram=int(cfg.get("text.C8_dedup.ngram", 5)),
                         threshold=float(cfg.get("text.C8_dedup.threshold", 0.85)))
    seen_exact: set[str] = set()

    jr = Journal(stage="corpus", lang=cfg.get("meta.lang_tgt", "lin"))
    jr.quarantine_count = 0

    qpath = out_dir / "quarantine.jsonl"

    with open(input_path, encoding="utf-8") as fin, \
            (out_dir / "manifest_corpus.jsonl").open("w", encoding="utf-8") as fout, \
            qpath.open("w", encoding="utf-8") as fq:
        for line in fin:
            if limit and jr.read >= limit:
                break
            rec = json.loads(line)
            row = Row(row_id=rec.get("row_id", ""), lang=rec.get("lang_tgt", ""),
                      source=rec.get("source", "unknown"), domain=rec.get("domain", ""),
                      text=rec.get("tgt", ""))

            # C1 schéma — rejet dur
            missing = [k for k in ("src", "tgt", "lang_src", "lang_tgt") if not rec.get(k)]
            if missing:
                jr.see_input(row)
                jr.drop(row, "C1_schema", f"champs manquants: {missing}")
                continue

            src = U.clean_text(rec["src"])
            tgt = U.clean_text(rec["tgt"])
            row.text = tgt
            toks = U.tokenize(tgt)
            jr.see_input(row, toks)

            # C2 unicité exacte — rejet dur
            key = exact_key(src, tgt)
            if key in seen_exact:
                jr.drop(row, "C2_exact_dedup", "doublon exact")
                continue
            seen_exact.add(key)

            # C4 longueur · C5 ratio · C7 alphabet — rejet dur ou bande grise
            warns: list[str] = []

            n = len(toks)
            b = _band(n, int(c4.get("min_words", 1)), int(c4.get("max_words", 200)),
                      int(c4.get("warn_min_words", n)), int(c4.get("warn_max_words", n)))
            if b == "reject":
                jr.drop(row, "C4_length", "longueur hors bornes", n)
                continue
            if b == "warn":
                warns.append("C4_length")

            ratio = len(tgt) / max(1, len(src))
            b = _band(ratio, float(c5.get("min", 0.4)), float(c5.get("max", 3.6)),
                      float(c5.get("warn_min", 0.0)), float(c5.get("warn_max", 1e9)))
            if b == "reject":
                jr.drop(row, "C5_ratio", "ratio hors bornes", round(ratio, 3))
                continue
            if b == "warn":
                warns.append("C5_ratio")

            ar = _alpha_ratio(tgt, LINGALA_ALPHABET)
            b = _band(ar, float(c7.get("min_ratio", 0.8)), None,
                      float(c7.get("warn_ratio", 0.0)), None)
            if b == "reject":
                jr.drop(row, "C7_alphabet", "alphabet cible hors norme", round(ar, 3))
                continue
            if b == "warn":
                warns.append("C7_alphabet")

            # C8 dédoublonnage approximatif — rejet dur
            if dedup.is_duplicate(row.row_id or key, tgt):
                jr.drop(row, "C8_dedup", "quasi-doublon")
                continue

            book = rec.get("book") or ""
            group = book if (book_aware and book) else tgt
            split = split_of(group, dev, test)
            payload = {
                "row_id": rec.get("row_id"), "src": src, "tgt": tgt,
                "lang_src": rec["lang_src"], "lang_tgt": rec["lang_tgt"],
                "domain": row.domain, "source": row.source,
                "license": rec.get("license"), "ref": rec.get("ref"),
                "book": book or None, "split": split,
            }

            if warns:
                payload["review"] = True
                payload["review_reasons"] = warns
                fq.write(json.dumps(payload, ensure_ascii=False) + "\n")
                jr.quarantine_count += 1
                continue

            fout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            jr.see_output(row, toks)

    jr.write_rejects(out_dir / "rejects.jsonl")
    return jr
