"""Tests golden — chaîne corpus (USFM, alignement, filtrage, config)."""
import json
import tempfile
import unittest
from pathlib import Path

from ml.corpus import align as A
from ml.corpus import filter_pairs as FP
from ml.corpus.config import load_corpus_config
from ml.corpus.usfm import clean_verse, parse_file

USFM = r"""
\id GEN Test Bible
\c 1
\s1 Titre de section
\p
\v 1 Au \w commencement|strong="H7225"\w*, Dieu \x a \xo 1.1 \xt Job 38:4.\x*créa les cieux.
\v 2 La terre était informe.
\p
\v 3 Dieu dit: Que la lumière soit!
"""


class TestUsfm(unittest.TestCase):
    def test_clean_verse_strips_markup(self):
        out = clean_verse(r'\w commencement|strong="H7225"\w* \x a \xo 1.1 \xt Job 38:4.\x*créa')
        self.assertEqual(out, "commencement créa")

    def test_parse_file_keys_and_sections_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "02-GENtest.usfm"
            p.write_text(USFM, encoding="utf-8")
            book, verses = parse_file(p)
        self.assertEqual(book, "GEN")
        self.assertEqual(set(v for _b, _c, v in verses), {1, 2, 3})
        self.assertEqual(verses[("GEN", 1, 1)],
                         "Au commencement, Dieu créa les cieux.")
        # le titre de section n'est pas injecté dans le texte du verset
        self.assertNotIn("Titre", verses[("GEN", 1, 1)])


class TestAlign(unittest.TestCase):
    def test_align_reports_mismatch(self):
        src = {("GEN", 1, 1): "a", ("GEN", 1, 2): "b", ("GEN", 1, 3): "c"}
        tgt = {("GEN", 1, 1): "x", ("GEN", 1, 3): "z"}
        pairs, report = A.align(src, tgt)
        self.assertEqual(report["aligned"], 2)
        self.assertEqual([(k, s, t) for k, s, t in pairs],
                         [(("GEN", 1, 1), "a", "x"), (("GEN", 1, 3), "c", "z")])
        self.assertEqual(report["src_only"], ["GEN.1.2"])
        self.assertEqual(report["tgt_only"], [])


class TestSplit(unittest.TestCase):
    def test_deterministic_and_partition(self):
        vals = [FP.split_of(f"GEN{i}", 0.05, 0.05) for i in range(200)]
        self.assertEqual(vals, [FP.split_of(f"GEN{i}", 0.05, 0.05) for i in range(200)])
        self.assertEqual(set(vals), {"train", "dev", "test"})


class TestConfig(unittest.TestCase):
    def test_gate_and_license(self):
        cfg = load_corpus_config()
        self.assertFalse(cfg.publishable)
        self.assertTrue(len(cfg.uncalibrated()) > 0)
        self.assertTrue(cfg.license_ok("CC-BY-SA-4.0 + domaine public"))
        self.assertFalse(cfg.license_ok("unknown"))
        self.assertFalse(cfg.license_ok("CC-BY-NC-4.0"))


class TestFilterPairs(unittest.TestCase):
    def test_run_filters_and_splits(self):
        cfg = load_corpus_config()
        with tempfile.TemporaryDirectory() as d:
            inp = Path(d) / "in.jsonl"
            rows = [
                {"row_id": "1", "src": "Au commencement Dieu créa",
                 "tgt": "Na ebandeli Nzambe akelaki", "lang_src": "fra",
                 "lang_tgt": "lin", "domain": "bible", "source": "ebible", "book": "GEN"},
                {"row_id": "2", "src": "Au commencement Dieu créa",
                 "tgt": "Na ebandeli Nzambe akelaki", "lang_src": "fra",
                 "lang_tgt": "lin", "domain": "bible", "source": "ebible", "book": "GEN"},  # doublon exact
                {"row_id": "3", "src": "une phrase francaise tres longue ici oui vraiment",
                 "tgt": "a",
                 "lang_src": "fra", "lang_tgt": "lin", "domain": "bible",
                 "source": "ebible", "book": "EXO"},  # ratio hors bornes dures
                {"row_id": "4", "src": "abcdefgh",
                 "tgt": "Nzambe akelaki mokili oyo",
                 "lang_src": "fra", "lang_tgt": "lin", "domain": "bible",
                 "source": "ebible", "book": "JOB"},  # ratio dans la bande grise
            ]
            inp.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            out = Path(d) / "out"
            jr = FP.run(cfg, inp, out)
            rep = jr.report()
            self.assertEqual(rep["read"], 4)
            self.assertGreaterEqual(rep["drops"].get("C2_exact_dedup", 0), 1)
            self.assertGreaterEqual(rep["drops"].get("C5_ratio", 0), 1)

            kept = [json.loads(l) for l in (out / "manifest_corpus.jsonl").read_text().splitlines()]
            self.assertEqual(len(kept), 1)
            self.assertTrue(all("split" in r and not r.get("review") for r in kept))

            # la paire douteuse part en quarantaine, pas à la poubelle
            self.assertEqual(jr.quarantine_count, 1)
            quar = [json.loads(l) for l in (out / "quarantine.jsonl").read_text().splitlines()]
            self.assertEqual(quar[0]["row_id"], "4")
            self.assertIn("C5_ratio", quar[0]["review_reasons"])


if __name__ == "__main__":
    unittest.main()
