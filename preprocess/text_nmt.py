"""Chaîne TEXTE (NMT) — T1..T11 (§4).

Entrée : JSONL `{"src","tgt","lang_src","lang_tgt","domain"}`.
Sortie : `manifest_nmt.jsonl` (schéma D10 + provenance de split).

Étapes model-backed (T6 langid, T9 parallélisme) et anti-fuite (T10) :
  - T6 utilise `fasttext lid.176` si `text.T6_langid.model_path` est fourni ;
  - T9 score le parallélisme (SONAR/LaBSE) si `text.T9_parallel.model_path` est fourni ;
  - T10 vérifie la fuite vers FLORES-200 devtest si le référentiel existe.
Sans l'outil, l'étape est **sautée et journalisée** — jamais silencieusement (§3.4).

Politique code-switching (D-a, trancher avant calibrage) : `policies.code_switching.nmt`
vaut `tolerant` (phrases mixtes conservées, `domain: code_switch`) ou `strict`.
"""
from __future__ import annotations

import json
from pathlib import Path

from .common import unicode_norm as U
from .common.config import Config, load_numerals
from .common.dedup import MinHashDedup, exact_key, stable_hash
from .common.journal import Journal, Row
from .common.langid import LangId
from .common.leak import LeakChecker
from .common.parallel import ParallelScorer


def _numerals(text: str, lang: str, table_for) -> str:
    """NFC + numéraux dans la langue concernée. Table absente => chiffres conservés."""
    table = table_for(lang)
    text = U.to_nfc(text)
    return U.normalize_numerals(text, table) if table else text


def _alpha_ratio(text: str, allowed: set[str]) -> float:
    letters = [c.lower() for c in U.to_nfc(text) if c.isalpha()]
    if not letters:
        return 0.0
    return sum(c in allowed for c in letters) / len(letters)


# Alphabet lingala courant (lettres + digrammes attestés). À valider (§4 T7).
LINGALA_ALPHABET = set("abcdefghiklmnoprstuvwyzŋɛɔáàâéèêíìîóòôúùû")


def run(cfg: Config, input_path: str | Path, out_dir: str | Path,
        limit: int | None = None) -> Journal:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    numerals_cache: dict[str, dict | None] = {}

    def numerals_for(lang: str):
        """Table de numéraux par langue (§4 T3). None si la langue n'a pas de table."""
        if lang not in numerals_cache:
            numerals_cache[lang] = load_numerals(lang=lang)
        return numerals_cache[lang]

    allowed = LINGALA_ALPHABET
    dedup = MinHashDedup(ngram=int(cfg.get("text.T8_minhash.ngram", 5)),
                         threshold=float(cfg.get("text.T8_minhash.threshold", 0.85)))
    langid = LangId(cfg.get("text.T6_langid.model_path"))
    scorer = ParallelScorer(str(cfg.get("text.T9_parallel.tool", "sonar")),
                            cfg.get("text.T9_parallel.model_path"))
    leak = LeakChecker(cfg.get("text.T10_leak.reference"))

    notes: list[str] = []
    if langid.method == "none":
        notes.append("T6_langid_saute (pas de modele lid.176)")
    if not scorer.available:
        notes.append("T9_parallel_saute (pas de modele SONAR/LaBSE)")
    if not leak.available:
        notes.append("T10_fuite_non_verifiee (pas de referentiel FLORES)")

    t5 = cfg.get("text.T5_length_ratio") or {}
    t4 = cfg.get("text.T4_length") or {}
    t7 = cfg.get("text.T7_alphabet") or {}
    policy = str(cfg.get("policies.code_switching.nmt", "strict"))
    min_ratio = float(t7.get("min_ratio", 0.90))
    hard_ratio = float(t7.get("hard_ratio", 0.55))
    min_cosine = float((cfg.get("text.T9_parallel") or {}).get("min_cosine", 0.55))
    dev = float(cfg.get("text.T11_split.dev", 0.02))
    test = float(cfg.get("text.T11_split.test", 0.02))
    seen_exact: set[str] = set()

    jr = Journal(stage="nmt", lang=cfg.lang)
    with open(input_path, encoding="utf-8") as fin, \
            (out_dir / "manifest_nmt.jsonl").open("w", encoding="utf-8") as fout:
        for line in fin:
            if limit and jr.read >= limit:
                break
            rec = json.loads(line)

            # T1 schéma — AVANT tout accès aux champs requis
            missing = [k for k in ("src", "tgt", "lang_src", "lang_tgt", "domain")
                       if not rec.get(k)]
            row = Row(row_id=rec.get("row_id") or exact_key(rec.get("src", ""), rec.get("tgt", "")),
                      lang=rec.get("lang_tgt", ""), source=rec.get("source", "unknown"),
                      domain=rec.get("domain", ""), text=rec.get("tgt", ""))
            if missing:
                jr.see_input(row)
                jr.drop(row, "T1_schema", f"champs manquants: {missing}")
                continue

            src = U.clean_text(_numerals(rec["src"], rec["lang_src"], numerals_for))
            tgt = U.clean_text(_numerals(rec["tgt"], rec["lang_tgt"], numerals_for))
            row.text = tgt
            toks = U.tokenize(tgt)
            jr.see_input(row, toks)

            # T2 unicité exacte
            key = exact_key(src, tgt)
            if key in seen_exact:
                jr.drop(row, "T2_exact_dedup", "doublon exact")
                continue
            seen_exact.add(key)

            # T4 longueur — D-b : `bucket` ne jette pas, `reject` jette
            bucket = None
            n = len(toks)
            if n < t4.get("min_words", 1) or n > t4.get("max_words", 50):
                beyond = t4.get("beyond", "bucket")
                if beyond == "reject":
                    jr.drop(row, "T4_length", "longueur hors bornes", n)
                    continue
                bucket = "T4_length"

            # T5 ratio
            ratio = len(tgt) / max(1, len(src))
            if not (t5.get("min", 0.5) <= ratio <= t5.get("max", 2.0)):
                jr.drop(row, "T5_length_ratio", "ratio hors bornes", round(ratio, 3))
                continue

            # T6 langid
            if langid.method != "none":
                res = langid.predict(tgt)
                if res.label != row.lang and res.confidence >= cfg.get("text.T6_langid.min_conf", 0.75):
                    jr.drop(row, "T6_langid", "langue détectée ≠ annoncée", res.label)
                    continue

            # T7 alphabet + politique code-switching (D-a)
            ar = _alpha_ratio(tgt, allowed)
            if ar < hard_ratio:
                jr.drop(row, "T7_alphabet", "alphabet hors langue (dur)", round(ar, 3))
                continue
            if ar < min_ratio:
                if policy == "tolerant":
                    row.domain = "code_switch"   # conservée, mais marquée
                else:
                    jr.drop(row, "T7_alphabet", "alphabet hors langue", round(ar, 3))
                    continue

            # T8 dédoublonnage approximatif
            if dedup.is_duplicate(row.row_id, tgt):
                jr.drop(row, "T8_dedup", "quasi-doublon")
                continue

            # T9 parallélisme (sauté sans modèle)
            if scorer.available:
                c = scorer.cosine(src, tgt)
                if c is not None and c < min_cosine:
                    jr.drop(row, "T9_parallel", "parallélisme faible", round(c, 3))
                    continue

            # T10 fuite vers le test (sautée sans référentiel)
            if leak.available and (leak.overlaps(src) or leak.overlaps(tgt)):
                jr.drop(row, "T10_leak", "chevauchement avec le test")
                continue

            # T11 découpage stable
            h = stable_hash(tgt, salt="split") / 2**64
            split = "test" if h < test else "dev" if h < test + dev else "train"

            fout.write(json.dumps({
                "src": src, "tgt": tgt, "lang_src": rec["lang_src"], "lang_tgt": rec["lang_tgt"],
                "domain": row.domain, "score": rec.get("score"), "source": row.source,
                "bucket": bucket, "split": split,
            }, ensure_ascii=False) + "\n")
            jr.see_output(row, toks)

    jr.write_rejects(out_dir / "rejects.jsonl")
    (out_dir / "run_notes.json").write_text(
        json.dumps({"notes": notes}, ensure_ascii=False, indent=2), encoding="utf-8")
    return jr
