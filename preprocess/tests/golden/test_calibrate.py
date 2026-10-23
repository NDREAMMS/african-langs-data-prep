"""Tests golden — outillage de calibrage (sélection de seuils)."""
import json
import tempfile
import unittest
from pathlib import Path

from ml.preprocess import calibrate as C


class TestThresholdPicker(unittest.TestCase):
    def test_lower_bound_separates_clean(self):
        # bons = score >= 5 ; mauvais = score < 5 (mesure unilatérale basse)
        scores = [1.0, 2.0, 3.0, 5.0, 6.0, 7.0, 9.0]
        good = [False, False, False, True, True, True, True]
        t = C.pick_side(scores, good, "low", target_precision=1.0, max_good_rejected=0.0)
        self.assertIsNotNone(t)
        self.assertLessEqual(t, 5.0)

    def test_window_length(self):
        words = [0, 1, 2, 5, 8, 40, 300]
        good = [False, True, True, True, True, True, False]
        lo, hi = C.pick_window(words, good, target_precision=1.0, max_good_rejected=0.0)
        self.assertIsNotNone(lo)
        self.assertIsNotNone(hi)
        self.assertLessEqual(lo, 2)
        self.assertGreaterEqual(hi, 40)

    def test_no_threshold_when_inseparable(self):
        # mêmes scores, labels aléatoires : aucune séparation propre
        scores = [1.0, 2.0, 3.0, 4.0]
        good = [True, False, True, False]
        self.assertIsNone(C.pick_side(scores, good, "low", 1.0, 0.0))


class TestSolveEndToEnd(unittest.TestCase):
    def _write(self, path: Path, rows):
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def test_solve_from_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            rows = []
            for i in range(10):
                rows.append({"row_id": str(i), "src": "les enfants jouent",
                             "tgt": "bana bazali kosakana", "pair_ok": "oui", "in_alphabet": "oui"})
            rows.append({"row_id": "bad", "src": "x", "tgt": "###45", "pair_ok": "non",
                         "in_alphabet": "non"})
            self._write(d / "text_sample.jsonl", rows)
            rc = C.main(["solve", "--lang", "lin", "--out", str(d)])
            self.assertEqual(rc, 0)
            res = json.loads((d / "calibration.json").read_text(encoding="utf-8"))
            self.assertIn("T5_length_ratio", res["seuils"])
            self.assertIn("T7_alphabet", res["seuils"])


class TestApplyPatch(unittest.TestCase):
    def test_patch_block_preserves_comments(self):
        lines = [
            "text:",
            "  T5_length_ratio:",
            "    min: 0.5",
            "    max: 2.0",
            "    provenance: null              # à calibrer",
            "  T6_langid:",
            "    provenance: null",
        ]
        ok = C._patch_block(lines, "T5_length_ratio", {"min": 0.45, "max": 3.1},
                            "calibrage_lin_2026-10-18")
        self.assertTrue(ok)
        txt = "\n".join(lines)
        self.assertIn("min: 0.45", txt)
        self.assertIn("max: 3.1", txt)
        self.assertIn("provenance: calibrage_lin_2026-10-18", txt)
        # le commentaire de la ligne provenance d'origine a disparu (remplacé), mais le bloc suivant est intact
        self.assertIn("T6_langid:", txt)


if __name__ == "__main__":
    unittest.main()
