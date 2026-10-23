"""Point d'entrée CLI du prétraitement.

Exemples :
    python -m ml.preprocess.run audio --limit 400
    python -m ml.preprocess.run nmt --input data/parallel/lin_fr.jsonl
    python -m ml.preprocess.run audio --allow-uncalibrated

Par défaut, un seuil non calibré (§2.2) BLOQUE la publication : le manifest est produit
pour inspection (mode brouillon) mais `report.json` porte `publishable: false`.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .common.config import load_config
from . import text_nmt
from .report import log_clearml, write_report

ROOT = Path(__file__).resolve().parents[2]


def _out_dir(lang: str, stage: str, run_id: str) -> Path:
    return ROOT / "data" / "processed" / lang / run_id / stage


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="preprocess")
    ap.add_argument("stage", choices=["audio", "nmt", "g2p"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--input", default=None, help="JSONL d'entrée (stage nmt)")
    ap.add_argument("--sources", default="bibletts,waxal", help="sources audio")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--allow-uncalibrated", action="store_true",
                    help="produire le manifest malgré des seuils non calibrés (brouillon)")
    ap.add_argument("--clearml", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    uncal = cfg.uncalibrated()
    if uncal and not args.allow_uncalibrated:
        print("SEUILS NON CALIBRÉS (§2.2) — publication bloquée :", file=sys.stderr)
        for s in uncal:
            print(f"  - {s}", file=sys.stderr)
        print("Relancer avec --allow-uncalibrated pour produire un manifest brouillon.",
              file=sys.stderr)
        return 2

    run_id = args.run_id or datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    out_dir = _out_dir(cfg.lang, args.stage, run_id)

    if args.stage == "audio":
        from . import audio_tts
        jr = audio_tts.run(cfg, out_dir, sources=args.sources.split(","), limit=args.limit)
    elif args.stage == "nmt":
        if not args.input:
            print("--input requis pour le stage nmt", file=sys.stderr)
            return 2
        jr = text_nmt.run(cfg, args.input, out_dir, limit=args.limit)
    else:
        print("stage g2p : bloqué sur la licence du lexique (D14), non implémenté.",
              file=sys.stderr)
        return 3

    report = write_report(cfg, jr, out_dir)
    if args.clearml:
        log_clearml(cfg, report, out_dir, args.stage)

    print(f"run_id     : {run_id}")
    print(f"sorties    : {out_dir}")
    print(f"lus/gardés : {report['read']}/{report['kept']}  publishable={report['publishable']}")
    if report["drops"]:
        print("rejets     :", ", ".join(f"{k}={v}" for k, v in report["drops"].items()))
    if uncal:
        print(f"[!] {len(uncal)} seuil(s) non calibré(s) — manifest = brouillon non publiable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
