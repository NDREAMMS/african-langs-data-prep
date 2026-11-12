"""Calibrage des seuils — étape 0' (§3 du document de prétraitement).

Instrument de l'étape 0 : il rend le calibrage **exécutable** sans dépendre d'un tableur.

Quatre sous-commandes :

  sample  — tire les échantillons à annoter (300 lignes texte, 200 paires, 100 clips/source)
            et écrit des gabarits d'annotation (JSONL + CSV à ouvrir par l'annotateur).
  solve   — lit les annotations remplies, calcule la valeur de chaque seuil qui satisfait
            la règle « ≥ 95 % de précision sur les rejets » et écrit `calibration_<lang>.json`.
  auto    — calcule les seuils sans annotation (percentiles sur données réelles, norme
            LUFS, hypothèses de littérature) et écrit `calibration_auto.json` + preuves.
  apply   — reporte les seuils calculés dans le YAML de config **avec leur provenance**
            (`calibrage_<lang>_<date>` ou `auto_<lang>_<date>` ; `--auto`) par édition
            ciblée, commentaires préservés.

Sans annotation humaine (labels vides), `solve` ne calcule rien et le signale : les
seuils restent `provenance: null` et les manifests restent `publishable: false` (§2.2).
En mode `validation: auto`, `apply --auto` admet `auto_*` et, pour les blocs listés dans
`hypothesis_blocks`, `hypothese_*` (décision D-f).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
from datetime import date
from pathlib import Path

import numpy as np

from .common import unicode_norm as U
from .common.config import load_config
from .text_nmt import LINGALA_ALPHABET, _alpha_ratio

ROOT = Path(__file__).resolve().parents[2]
FIELDS = {
    "text": ["lang_id_ok", "pair_ok", "in_alphabet"],
    "pairs": ["align_ok", "tgt_ok"],
    "audio": ["quality_ok", "text_match_ok"],
}


# ---------------------------------------------------------------------------
# Sélection de seuils (cœur testable, indépendant des données)
# ---------------------------------------------------------------------------
def _stats(rejected_idx, good) -> tuple[int, int, float]:
    n_rej = len(rejected_idx)
    bad_in_rej = sum(1 for i in rejected_idx if not good[i])
    prec = bad_in_rej / n_rej if n_rej else 0.0
    return n_rej, bad_in_rej, prec


def pick_side(scores: list[float], good: list[bool], side: str,
              target_precision: float = 0.95, max_good_rejected: float = 0.05):
    """Seuil unilatéral : rejette `score < t` (side='low') ou `score > t` (side='high').

    Parmi les seuils qui atteignent la précision cible sur les rejets ET rejettent au plus
    `max_good_rejected` des bons, retient celui qui garde le plus de bons (puis le moins agressif).
    """
    n_good = sum(good) or 1
    best = None
    for t in sorted(set(scores)):
        idx = [i for i, s in enumerate(scores) if (s < t if side == "low" else s > t)]
        if not idx:
            continue
        n_rej, _bad, prec = _stats(idx, good)
        good_rej = sum(1 for i in idx if good[i]) / n_good
        if prec >= target_precision and good_rej <= max_good_rejected:
            cand = (good_rej, t)
            if best is None or cand < best:
                best = cand
    return best[1] if best else None


def pick_window(scores: list[float], good: list[bool],
                target_precision: float = 0.95, max_good_rejected: float = 0.05):
    """Fenêtre [lo, hi] : rejette hors bornes. Renvoie (lo, hi) ou (None, None)."""
    lo = pick_side(scores, good, "low", target_precision, max_good_rejected)
    hi = pick_side(scores, good, "high", target_precision, max_good_rejected)
    return lo, hi


# ---------------------------------------------------------------------------
# sample
# ---------------------------------------------------------------------------
def _load_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if limit and len(out) >= limit:
                break
            out.append(json.loads(line))
    return out


def _write_sample(rows: list[dict], out_dir: Path, name: str, label_fields: list[str]):
    js = out_dir / f"{name}_sample.jsonl"
    with js.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    cs = out_dir / f"{name}_sample.csv"
    cols = list(rows[0].keys()) if rows else []
    with cs.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  {name:<6} : {len(rows):>4} items → {js.name} / {cs.name}  (à remplir : {label_fields})")


def cmd_sample(args) -> int:
    out_dir = Path(args.out) if args.out else ROOT / "data" / "calibration" / args.lang
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    src = Path(args.input) if args.input else ROOT / "data" / "parallel" / "lin_fr.jsonl"
    rows = _load_jsonl(src)
    print(f"source parallèle : {src} ({len(rows)} paires)")

    rng.shuffle(rows)
    text_rows = []
    for r in rows[:args.n_text]:
        text_rows.append({"row_id": r.get("row_id"), "src": r.get("src"), "tgt": r.get("tgt"),
                          **{f: "" for f in FIELDS["text"]}})
    pairs_rows = []
    for r in rows[args.n_text:args.n_text + args.n_pairs]:
        pairs_rows.append({"row_id": r.get("row_id"), "src": r.get("src"), "tgt": r.get("tgt"),
                           **{f: "" for f in FIELDS["pairs"]}})
    _write_sample(text_rows, out_dir, "text", FIELDS["text"])
    _write_sample(pairs_rows, out_dir, "pairs", FIELDS["pairs"])

    audio_rows = _sample_audio(args, out_dir, rng)
    _write_sample(audio_rows, out_dir, "audio", FIELDS["audio"])
    print(f"échantillons     : {out_dir}")
    return 0


def _sample_audio(args, out_dir: Path, rng) -> list[dict]:
    from .audio_sources import iter_bibletts, iter_waxal, load_audio
    import soundfile as sf

    clips_dir = out_dir / "clips"
    clips_dir.mkdir(exist_ok=True)
    sources = args.sources.split(",")
    per = max(1, args.n_audio // max(1, len(sources)))
    rows: list[dict] = []
    for s in sources:
        items = []
        if s == "bibletts":
            items = list(iter_bibletts("data/bibletts/extracted", splits=("dev",)))
        elif s == "waxal":
            items = list(iter_waxal("data/waxal/asr/lin", split="train", limit=per * 4))
        rng.shuffle(items)
        for it in items[:per]:
            audio_ref = it.path
            try:
                it = load_audio(it)
                out_wav = clips_dir / f"{it.row.row_id}.wav"
                if not out_wav.exists():
                    sf.write(str(out_wav), it.samples, it.sr)
                audio_ref = str(out_wav.relative_to(out_dir))
            except Exception:
                pass
            rows.append({"row_id": it.row.row_id, "audio": audio_ref, "text": it.row.text,
                         "source": it.row.source, "domain": it.row.domain,
                         **{f: "" for f in FIELDS["audio"]}})
    return rows


# ---------------------------------------------------------------------------
# solve
# ---------------------------------------------------------------------------
def _label(row: dict, field: str) -> bool | None:
    v = str(row.get(field, "")).strip().lower()
    if v in ("", "none", "null"):
        return None
    return v in ("1", "true", "oui", "yes", "ok", "y", "vrai")


def _annotated(rows: list[dict], field: str) -> tuple[list[dict], list[bool]] | None:
    kept = []
    for r in rows:
        lab = _label(r, field)
        if lab is not None:
            kept.append((r, lab))
    if not kept:
        return None
    return [r for r, _ in kept], [lab for _, lab in kept]


def cmd_solve(args) -> int:
    out_dir = Path(args.out) if args.out else ROOT / "data" / "calibration" / args.lang
    result: dict = {"lang": args.lang, "seuils": {}, "non_calcules": []}

    # --- texte : T4 longueur, T5 ratio, T7 alphabet ---
    text_path = out_dir / "text_sample.jsonl"
    if text_path.exists():
        rows = _load_jsonl(text_path)
        ann = _annotated(rows, "pair_ok")
        if ann:
            items, good = ann
            words = [len(U.tokenize(r["tgt"])) for r in items]
            ratios = [len(r["tgt"]) / max(1, len(r["src"])) for r in items]
            lo, hi = pick_window(words, good, args.target_precision, args.max_good_rejected)
            result["seuils"]["T4_length"] = {"min_words": lo, "max_words": hi}
            rlo, rhi = pick_window(ratios, good, args.target_precision, args.max_good_rejected)
            result["seuils"]["T5_length_ratio"] = {"min": rlo, "max": rhi}
        else:
            result["non_calcules"].append("T4_length/T5_length_ratio (pas d'annotation pair_ok)")
        ann = _annotated(rows, "in_alphabet")
        if ann:
            items, good = ann
            ratios = [_alpha_ratio(r["tgt"], LINGALA_ALPHABET) for r in items]
            lo = pick_side(ratios, good, "low", args.target_precision, args.max_good_rejected)
            result["seuils"]["T7_alphabet"] = {"min_ratio": lo}
        else:
            result["non_calcules"].append("T7_alphabet (pas d'annotation in_alphabet)")
    else:
        result["non_calcules"].append("text_sample.jsonl absent")

    # --- filtres model-backed : nécessitent les scores (modèles fournis) ---
    for f in ("T6_langid", "T8_minhash", "T9_parallel", "C8_dedup",
              "A5_duration", "A6_rate", "A7_dnsmos", "A8_snr", "A9_asr_wer", "A3_loudness"):
        result["non_calcules"].append(f"{f} (score modèle/mesure requis)")

    (out_dir / "calibration.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rapport : {out_dir / 'calibration.json'}")
    print(f"calculés : {sorted(result['seuils'])}")
    print(f"à faire  : {len(result['non_calcules'])} seuil(s) sans score exploitable")
    return 0


# ---------------------------------------------------------------------------
# auto — calibrage sans annotation (décision « sans relecteur »)
# ---------------------------------------------------------------------------
def _summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    a = np.asarray(values, dtype=float)
    return {
        "n": int(a.size),
        "min": float(a.min()),
        "p05": float(np.percentile(a, 0.5)),
        "p1": float(np.percentile(a, 1)),
        "p5": float(np.percentile(a, 5)),
        "p50": float(np.percentile(a, 50)),
        "p95": float(np.percentile(a, 95)),
        "p99": float(np.percentile(a, 99)),
        "max": float(a.max()),
    }


def _rows_hash(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for r in rows:
        h.update(json.dumps(r, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()[:12]


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text_input(args) -> Path | None:
    candidates = [Path(args.input)] if args.input else [
        ROOT / "data" / "parallel" / "lin_fr.jsonl",
        ROOT / "data" / "corpus" / "lin_fr_v2" / "manifest_corpus.jsonl",
        ROOT / "data" / "corpus" / "lin_fr_v2" / "splits" / "train.jsonl",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _collect_audio_stats(args, cfg) -> dict:
    """Échantillonne BibleTTS/WAXAL et mesure durée, débit, SNR, DNSMOS."""
    from .audio_sources import iter_bibletts, iter_waxal, load_audio
    from .audio_tts import Dnsmos, estimate_snr_db, words_per_second

    rng = random.Random(args.seed)
    sources = [s for s in args.sources.split(",") if s]
    per = max(1, args.n_audio // max(1, len(sources)))
    snr_backend = str(cfg.get("audio.A8_snr.backend", "simple"))
    a7_path = cfg.get("audio.A7_dnsmos.model_path")
    dnsmos = Dnsmos(a7_path) if a7_path and Path(a7_path).exists() else None

    out = {"durations": [], "rates": [], "snrs": [], "dnsmos": [],
           "by_source": {}, "errors": [], "ids": [], "skipped": 0}
    for source in sources:
        try:
            if source == "bibletts":
                items = list(iter_bibletts("data/bibletts/extracted", splits=("dev",)))
            elif source == "waxal":
                items = list(iter_waxal("data/waxal/asr/lin", split="train", limit=per * 4))
            else:
                out["errors"].append(f"{source}: source inconnue")
                continue
        except Exception as e:
            out["errors"].append(f"{source}: {type(e).__name__}")
            continue
        rng.shuffle(items)
        kept = 0
        for item in items[:per]:
            try:
                item = load_audio(item)
                if item.samples.size == 0 or item.sr <= 0:
                    continue
                dur = len(item.samples) / item.sr
                out["durations"].append(dur)
                out["rates"].append(words_per_second(item.row.text, dur))
                out["snrs"].append(estimate_snr_db(item.samples, item.sr, backend=snr_backend))
                if dnsmos is not None:
                    score = dnsmos.score(item.samples, item.sr)
                    if score is not None:
                        out["dnsmos"].append(score)
                out["ids"].append(item.row.row_id)
                kept += 1
            except Exception:
                out["skipped"] += 1
                continue
        out["by_source"][source] = kept
        if kept == 0:
            out["errors"].append(f"{source}: aucun clip lisible")
    return out


def cmd_auto(args) -> int:
    out_dir = Path(args.out) if args.out else ROOT / "data" / "calibration" / args.lang
    ev_dir = out_dir / "evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(args.config)
    lang = args.lang
    today = date.today().isoformat()

    result: dict = {"lang": lang, "date": today, "mode": "auto",
                    "seuils": {}, "non_calcules": [], "sources": {}}

    def add(block: str, values: dict, method: str, summary: dict, data_hash: str,
            source: str) -> None:
        ev = ev_dir / f"{block}.json"
        ev.write_text(json.dumps({
            "block": block, "method": method, "lang": lang, "date": today,
            "input": source, "data_hash": data_hash, "summary": summary,
            "values": values,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        result["seuils"][block] = {
            **values,
            "provenance": f"auto_{method}_{lang}_{today}",
            "evidence": _rel(ev),
            "method": method,
        }

    # -- texte --------------------------------------------------------------
    text_path = _text_input(args)
    if text_path is None:
        result["non_calcules"].append("texte: aucun JSONL trouvé (utiliser --input)")
    else:
        rows = [r for r in _load_jsonl(text_path, args.n_text)
                if r.get("src") and r.get("tgt")]
        if not rows:
            result["non_calcules"].append(f"texte: aucune paire exploitable dans {text_path}")
        else:
            data_hash = _rows_hash(rows)
            result["sources"]["texte"] = {"input": _rel(text_path), "n": len(rows),
                                          "data_hash": data_hash}

            words = [len(U.tokenize(r["tgt"])) for r in rows]
            ratios = [len(r["tgt"]) / max(1, len(r["src"])) for r in rows]
            alpha = [_alpha_ratio(r["tgt"], LINGALA_ALPHABET) for r in rows]

            sw = _summary(words)
            add("T4_length", {
                "min_words": max(1, int(math.floor(sw["p1"]))),
                "max_words": max(1, int(math.ceil(sw["p99"]))),
            }, "percentile_p1_p99", sw, data_hash, _rel(text_path))

            sr = _summary(ratios)
            add("T5_length_ratio", {
                "min": round(max(0.1, sr["p1"]), 3),
                "max": round(min(10.0, sr["p99"]), 3),
            }, "percentile_p1_p99", sr, data_hash, _rel(text_path))

            sa = _summary(alpha)
            add("T7_alphabet", {
                "min_ratio": round(sa["p1"], 3),
                "hard_ratio": round(min(sa["p05"], sa["p1"]), 3),
            }, "percentile_p1_p05", sa, data_hash, _rel(text_path))

            # T6/T9 : seulement si les modèles sont fournis.
            t6_model = cfg.get("text.T6_langid.model_path")
            if t6_model and Path(t6_model).exists():
                from .common.langid import LangId
                lid = LangId(t6_model)
                conf = [lid.predict(r["tgt"]).confidence for r in rows]
                s6 = _summary(conf)
                add("T6_langid", {"min_conf": round(max(0.0, s6["p5"]), 3)},
                    "percentile_p5", s6, data_hash, _rel(text_path))
            else:
                result["non_calcules"].append("T6_langid (modèle fastText absent)")

            t9_model = cfg.get("text.T9_parallel.model_path")
            if t9_model:
                from .common.parallel import ParallelScorer
                scorer = ParallelScorer(str(cfg.get("text.T9_parallel.tool", "sonar")),
                                        t9_model)
                if scorer.available:
                    cos = [c for r in rows if (c := scorer.cosine(r["src"], r["tgt"])) is not None]
                    s9 = _summary(cos)
                    add("T9_parallel", {"min_cosine": round(max(0.0, s9["p5"]), 3)},
                        "percentile_p5", s9, data_hash, _rel(text_path))
                else:
                    result["non_calcules"].append("T9_parallel (modèle indisponible)")
            else:
                result["non_calcules"].append("T9_parallel (modèle absent)")

    # -- audio --------------------------------------------------------------
    if args.no_audio:
        result["non_calcules"].append("audio: --no-audio")
    else:
        stats = _collect_audio_stats(args, cfg)
        result["sources"]["audio"] = {
            "by_source": stats["by_source"],
            "n": len(stats["ids"]),
            "skipped": stats["skipped"],
            "errors": stats["errors"],
        }
        if stats["durations"]:
            data_hash = hashlib.sha256(
                json.dumps(stats["ids"], sort_keys=True).encode()
            ).hexdigest()[:12]
            sd = _summary(stats["durations"])
            add("A5_duration", {
                "min_s": round(max(0.5, sd["p1"]), 2),
                "max_s": round(min(30.0, sd["p99"]), 2),
            }, "percentile_p1_p99", sd, data_hash, "audio")
            sr = _summary(stats["rates"])
            add("A6_rate", {"max_words_per_s": round(sr["p95"], 2)},
                "percentile_p95", sr, data_hash, "audio")
        else:
            result["non_calcules"].append("A5_duration/A6_rate (aucun clip chargé)")
        if stats["snrs"]:
            ss = _summary(stats["snrs"])
            add("A8_snr", {"min_db": round(max(0.0, ss["p5"]), 1)},
                "percentile_p5", ss, data_hash, "audio")
        else:
            result["non_calcules"].append("A8_snr (aucune mesure)")
        if stats["dnsmos"]:
            s7 = _summary(stats["dnsmos"])
            add("A7_dnsmos", {"min": round(max(0.0, s7["p5"]), 2)},
                "percentile_p5", s7, data_hash, "audio")
        else:
            result["seuils"]["A7_dnsmos"] = {
                "provenance": f"hypothese_{lang}_{today}",
                "method": "hypothese_litterature", "evidence": None,
            }
        result["non_calcules"].append("A9_asr_wer (MMS interdit D6 ; remplacer par M3)")

    # Blocs structurels / normatifs : hypothèse documentée, pas de calcul.
    result["seuils"].setdefault("T8_minhash", {
        "provenance": f"hypothese_{lang}_{today}",
        "method": "structural", "evidence": None,
    })
    result["seuils"].setdefault("A3_loudness", {
        "provenance": f"hypothese_{lang}_{today}",
        "method": "norme_lufs", "evidence": None,
    })

    (out_dir / "calibration_auto.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rapport auto : {out_dir / 'calibration_auto.json'}")
    print(f"preuves      : {ev_dir}")
    print(f"calculés     : {sorted(result['seuils'])}")
    print(f"non calculés : {len(result['non_calcules'])}")
    for n in result["non_calcules"]:
        print(f"  - {n}")
    return 0


# ---------------------------------------------------------------------------
# apply — édition ciblée du YAML (commentaires préservés)
# ---------------------------------------------------------------------------
def _patch_block(lines: list[str], block: str, values: dict, provenance: str,
                 evidence: str | None = None) -> bool:
    """Remplace les champs numériques d'un bloc YAML, sa `provenance` et sa preuve."""
    header = re.compile(rf"^(\s*){re.escape(block)}:\s*(#.*)?$")
    start = None
    for i, ln in enumerate(lines):
        if header.match(ln):
            start = i
            indent = len(ln) - len(ln.lstrip())
            break
    if start is None:
        return False
    end = len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j]
        if s.strip() and (len(s) - len(s.lstrip())) <= indent and not s.lstrip().startswith("#"):
            end = j
            break
    prov_idx = None
    for i in range(start + 1, end):
        for key, val in values.items():
            if val is None:
                continue
            m = re.match(rf"^(\s*){re.escape(key)}:\s*([^#]*?)\s*(#.*)?$", lines[i])
            if m:
                comment = f"  {m.group(3)}" if m.group(3) else ""
                lines[i] = f"{m.group(1)}{key}: {val}{comment}"
        if re.match(r"^\s*provenance:\s*", lines[i]):
            ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
            lines[i] = f"{ind}provenance: {provenance}"
            prov_idx = i
    if evidence is not None and prov_idx is not None:
        ind = lines[prov_idx][:len(lines[prov_idx]) - len(lines[prov_idx].lstrip())]
        ev_idx = next((i for i in range(start + 1, end)
                       if re.match(r"^\s*evidence:\s*", lines[i])), None)
        if ev_idx is None:
            lines.insert(prov_idx + 1, f"{ind}evidence: {evidence}")
        else:
            lines[ev_idx] = f"{ind}evidence: {evidence}"
    return True


def cmd_apply(args) -> int:
    out_dir = Path(args.out) if args.out else ROOT / "data" / "calibration" / args.lang
    auto = bool(getattr(args, "auto", False))
    fname = "calibration_auto.json" if auto else "calibration.json"
    data = json.loads((out_dir / fname).read_text(encoding="utf-8"))
    seuils = data.get("seuils", {})
    if not seuils:
        print(f"aucun seuil calculé dans {fname} — rien à appliquer.")
        return 1
    default_prov = f"calibrage_{args.lang}_{date.today().isoformat()}"
    cfg_path = Path(args.config) if args.config else (
        ROOT / "ml" / "preprocess" / "configs" / "preprocess.yaml")
    lines = cfg_path.read_text(encoding="utf-8").splitlines()
    applied, skipped = [], []
    for block, payload in seuils.items():
        if auto:
            prov = payload.get("provenance") or default_prov
            evidence = payload.get("evidence")
            values = {k: v for k, v in payload.items()
                      if k not in ("provenance", "evidence", "method")}
        else:
            prov, evidence, values = default_prov, None, payload
        if _patch_block(lines, block, values, prov, evidence):
            applied.append(block)
        else:
            skipped.append(block)
    cfg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"appliqué : {applied}")
    if skipped:
        print(f"introuvables : {skipped}")
    mode = "auto" if auto else "human"
    print(f"provenance : mode={mode}  → {cfg_path}")
    print("Relancer la chaîne : le manifest devient publiable si les gates passent.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="calibrate", description="Calibrage des seuils (étape 0')")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="tirer les échantillons à annoter")
    s.add_argument("--lang", default="lin")
    s.add_argument("--input", default=None)
    s.add_argument("--out", default=None)
    s.add_argument("--sources", default="bibletts,waxal")
    s.add_argument("--n-text", type=int, default=300)
    s.add_argument("--n-pairs", type=int, default=200)
    s.add_argument("--n-audio", type=int, default=100)
    s.add_argument("--seed", type=int, default=20261018)
    s.set_defaults(func=cmd_sample)

    s = sub.add_parser("solve", help="calculer les seuils depuis les annotations")
    s.add_argument("--lang", default="lin")
    s.add_argument("--out", default=None)
    s.add_argument("--target-precision", type=float, default=0.95)
    s.add_argument("--max-good-rejected", type=float, default=0.05)
    s.set_defaults(func=cmd_solve)

    s = sub.add_parser("auto", help="calibrer automatiquement, sans annotation")
    s.add_argument("--lang", default="lin")
    s.add_argument("--input", default=None)
    s.add_argument("--out", default=None)
    s.add_argument("--config", default=None)
    s.add_argument("--sources", default="bibletts,waxal")
    s.add_argument("--n-text", type=int, default=5000)
    s.add_argument("--n-audio", type=int, default=100)
    s.add_argument("--seed", type=int, default=20261102)
    s.add_argument("--no-audio", action="store_true")
    s.set_defaults(func=cmd_auto)

    s = sub.add_parser("apply", help="reporter les seuils dans la config (provenance)")
    s.add_argument("--lang", default="lin")
    s.add_argument("--out", default=None)
    s.add_argument("--config", default=None)
    s.add_argument("--auto", action="store_true",
                   help="appliquer calibration_auto.json (provenances auto_/hypothese_)")
    s.set_defaults(func=cmd_apply)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
