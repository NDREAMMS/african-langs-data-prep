"""Point d'entrée CLI du prétraitement.

Exemples :
    python -m ml.preprocess.run audio --limit 400
    python -m ml.preprocess.run nmt --input data/parallel/lin_fr.jsonl
    python -m ml.preprocess.run audio --allow-draft

Par défaut, un seuil sans provenance admise (mode `validation`) BLOQUE la publication.
`--allow-draft` produit le manifest pour inspection ; `report.json` porte alors
`publishable: false`, `validation_level: blocked` et le détail des gates.
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
    ap.add_argument("--allow-draft", "--allow-uncalibrated", dest="allow_draft",
                    action="store_true",
                    help="produire un manifest brouillon malgré des seuils bloqués")
    ap.add_argument("--clearml", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    blocked = cfg.blocked_blocks()
    if blocked and not args.allow_draft:
        print("SEUILS BLOQUÉS (politique de validation) — publication bloquée :",
              file=sys.stderr)
        for s in blocked:
            print(f"  - {s}", file=sys.stderr)
        print("Lancer `python -m ml.preprocess.calibrate auto --lang "
              f"{cfg.lang}` puis `apply --auto`, ou relancer avec --allow-draft.",
              file=sys.stderr)
        return 2
    if blocked:
        print(f"[brouillon] {len(blocked)} bloc(s) sans provenance admise — "
              "manifest non publiable.", file=sys.stderr)
    elif cfg.validation_level == "auto_unvalidated":
        print("[validation] seuils auto-calibrés — validation_level=auto_unvalidated.",
              file=sys.stderr)

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
    print(f"validation : {report['validation_level']}  gates={'OK' if report['gates']['ok'] else 'KO'}")
    if report["drops"]:
        print("rejets     :", ", ".join(f"{k}={v}" for k, v in report["drops"].items()))
    if not report["publishable"]:
        print("[!] " + " | ".join(report["publishable_reason"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
