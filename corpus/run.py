"""Point d'entrée CLI de la chaîne corpus.

    python -m ml.corpus.run audit                 # inventaire + licences des sources
    python -m ml.corpus.run align                 # aligne USFM FR ↔ lin → JSONL
    python -m ml.corpus.run build --limit 500     # filtre/dédoublonne/découpe
    python -m ml.corpus.run stats                 # statistiques du manifest

Comme le prétraitement (§2.2), un seuil non calibré BLOQUE la publication du
corpus : `build` sort en code 2 sans `--allow-uncalibrated` (mode brouillon).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import align as A
from . import filter_pairs
from .config import load_corpus_config
from .sources import audit as audit_sources
from .sources import load_registry

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "data" / "corpus"


def _cmd_audit(args) -> int:
    cfg = load_corpus_config(args.config)
    registry = load_registry()
    table = audit_sources(registry, ROOT, cfg)
    out = CORPUS_DIR / "audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
    for e in table:
        flag = "OK " if e.get("license_admise") else "REF"
        pres = "present" if e["present"] else "absent "
        lic = "perms" if e["permis"] else "non-perms"
        n = e.get("files") or (1 if e["present"] else 0)
        print(f"[{flag}] {e['id']:<22} {pres} {lic:<10} fichiers={n}  {e['license']}")
    print(f"\nregistre : {out}")
    return 0


def _cmd_align(args) -> int:
    raw = CORPUS_DIR / "raw" / "ebible"
    out = CORPUS_DIR / "aligned" / "lin_fr.jsonl"
    report = A.build_bible(raw / "fraLSG", raw / "lin", out)
    (CORPUS_DIR / "aligned" / "align_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"versets alignés : {report['aligned']}")
    print(f"  FR seul      : {len(report['src_only'])}")
    print(f"  lin seul     : {len(report['tgt_only'])}")
    print(f"sortie         : {out}")
    return 0


def _cmd_build(args) -> int:
    cfg = load_corpus_config(args.config)
    uncal = cfg.uncalibrated()
    if uncal and not args.allow_uncalibrated:
        print("SEUILS CORPUS NON CALIBRÉS (§2.2) — publication bloquée :", file=sys.stderr)
        for s in uncal:
            print(f"  - {s}", file=sys.stderr)
        print("Relancer avec --allow-uncalibrated pour produire un corpus brouillon.",
              file=sys.stderr)
        return 2

    run_id = args.run_id or datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    out_dir = CORPUS_DIR / run_id
    src = Path(args.input) if args.input else CORPUS_DIR / "aligned" / "lin_fr.jsonl"
    if not src.exists():
        print(f"entrée absente : {src} (lancer `align` d'abord)", file=sys.stderr)
        return 2

    jr = filter_pairs.run(cfg, src, out_dir, limit=args.limit)
    report = jr.report()
    report.update({"run_id": run_id, "cfg_hash": cfg.hash, "publishable": cfg.publishable,
                   "uncalibrated": uncal, "source": str(src),
                   "quarantine": getattr(jr, "quarantine_count", 0)})
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # découpage en fichiers train/dev/test
    splits: dict[str, list] = {"train": [], "dev": [], "test": []}
    with (out_dir / "manifest_corpus.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            splits.setdefault(rec["split"], []).append(rec)
    (out_dir / "splits").mkdir(exist_ok=True)
    for name, recs in splits.items():
        with (out_dir / "splits" / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
            for rec in recs:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # export vers l'entrée du prétraitement NMT
    export = ROOT / "data" / "parallel" / "lin_fr.jsonl"
    export.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out_dir / "manifest_corpus.jsonl", export)

    print(f"run_id     : {run_id}")
    print(f"sorties    : {out_dir}")
    print(f"lus/gardés : {report['read']}/{report['kept']}  publishable={report['publishable']}")
    print(f"quarantaine: {report.get('quarantine', 0)}  → {out_dir / 'quarantine.jsonl'}")
    if report["drops"]:
        print("rejets     :", ", ".join(f"{k}={v}" for k, v in report["drops"].items()))
    print("splits     :", ", ".join(f"{k}={len(v)}" for k, v in splits.items()))
    print(f"export     : {export}")
    if uncal:
        print(f"[!] {len(uncal)} seuil(s) non calibré(s) — corpus = brouillon non publiable.")
    return 0


def _cmd_stats(args) -> int:
    path = Path(args.input) if args.input else CORPUS_DIR / "aligned" / "lin_fr.jsonl"
    n = 0
    dom = Counter()
    book = Counter()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            n += 1
            dom[rec.get("domain", "?")] += 1
            book[rec.get("book", "?")] += 1
    print(f"paires   : {n}  ({path})")
    print(f"domaines : {dict(dom)}")
    print(f"livres   : {len([b for b in book if b != '?'])} livres bibliques")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="corpus")
    ap.add_argument("stage", choices=["audit", "align", "build", "stats"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--input", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--allow-uncalibrated", action="store_true")
    args = ap.parse_args(argv)
    return {"audit": _cmd_audit, "align": _cmd_align,
            "build": _cmd_build, "stats": _cmd_stats}[args.stage](args)


if __name__ == "__main__":
    raise SystemExit(main())
