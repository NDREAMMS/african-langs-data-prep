"""Tests golden — politique de validation, calibrage auto, gates (D-f)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ml.preprocess import calibrate as C
from ml.preprocess.common.config import CALIBRABLE, Config, load_config
from ml.preprocess.gates import evaluate


def _cfg(mode="auto", text_prov=None, audio_prov=None, hypothesis=True):
    raw = {
        "meta": {"lang": "lin"},
        "validation": {
            "mode": mode,
            "allow_hypothesis": hypothesis,
            "hypothesis_blocks": ["T8_minhash", "A3_loudness"],
            "gates": {
                "min_retention_tokens": 0.80,
                "min_retention_vocab": 0.50,
                "min_source_retention": 0.20,
                "max_single_filter_share": 0.50,
                "max_clipping_rate": 0.01,
                "require_no_wiped_speakers": True,
            },
        },
        "text": {b: {"provenance": text_prov} for b in CALIBRABLE if b.startswith("T")},
        "audio": {b: {"provenance": audio_prov} for b in CALIBRABLE if b.startswith("A")},
    }
    return Config(raw=raw, path=Path("/tmp/preprocess.yaml"), hash="test")


class TestConfigStatus(unittest.TestCase):
    def test_human_requires_calibrage(self):
        c = _cfg("human", "calibrage_lin_2026-11-02", "calibrage_lin_2026-11-02")
        self.assertEqual(c.status(), "human")
        self.assertEqual(c.validation_level, "human_validated")
        self.assertTrue(c.publishable)

    def test_auto_accepts_auto_provenance(self):
        c = _cfg("auto", "auto_percentile_p1_p99_lin_2026-11-02",
                 "auto_percentile_p5_lin_2026-11-02")
        self.assertEqual(c.status(), "auto")
        self.assertEqual(c.validation_level, "auto_unvalidated")
        self.assertTrue(c.publishable)

    def test_null_provenance_is_blocked(self):
        c = _cfg("auto", None, None)
        self.assertEqual(c.status(), "blocked")
        self.assertFalse(c.publishable)
        self.assertEqual(len(c.blocked_blocks()), len(CALIBRABLE))

    def test_human_rejects_auto_provenance(self):
        c = _cfg("human", "auto_x_lin_2026-11-02", "auto_x_lin_2026-11-02")
        self.assertEqual(c.status(), "blocked")

    def test_hypothesis_only_on_whitelist(self):
        c = _cfg("auto", "hypothese_lin_2026-11-02", "hypothese_lin_2026-11-02")
        # T4/T5/T6/T7/T9 et A5/A6/A7/A8/A9 ne sont pas dans la liste → bloqués
        self.assertIn("text.T4_length", c.blocked_blocks())
        self.assertIn("audio.A5_duration", c.blocked_blocks())
        # les blocs whitelist sont acceptés
        self.assertNotIn("text.T8_minhash", c.blocked_blocks())
        self.assertNotIn("audio.A3_loudness", c.blocked_blocks())

    def test_shipped_config_is_blocked_before_auto(self):
        # le YAML livré est en mode auto mais sans provenance → toujours bloqué
        c = load_config()
        self.assertEqual(c.validation_mode(), "auto")
        self.assertFalse(c.publishable)


def _report(**over):
    rep = {
        "read": 100,
        "kept": 95,
        "drops": {"A8_snr": 5},
        "retention": {
            "tokens": 0.95,
            "vocab_unique": 0.90,
            "by_source": {"bibletts": 0.95},
            "speakers": {"total": 1, "kept": 1, "wiped": []},
        },
    }
    rep.update(over)
    return rep


class TestGates(unittest.TestCase):
    def setUp(self):
        self.cfg = _cfg("auto", "auto_x_lin_2026-11-02", "auto_x_lin_2026-11-02")

    def test_clean_report_passes(self):
        g = evaluate(_report(), self.cfg)
        self.assertTrue(g["ok"], g)

    def test_empty_output_fails(self):
        g = evaluate(_report(kept=0), self.cfg)
        self.assertFalse(g["ok"])
        self.assertIn("kept_nonzero", g["failures"])

    def test_low_token_retention_fails(self):
        rep = _report(retention={**_report()["retention"], "tokens": 0.5})
        g = evaluate(rep, self.cfg)
        self.assertIn("retention_tokens", g["failures"])

    def test_wiped_source_fails(self):
        rep = _report(retention={**_report()["retention"], "by_source": {"waxal": 0.0}})
        g = evaluate(rep, self.cfg)
        self.assertIn("source_retention", g["failures"])

    def test_wiped_speaker_fails(self):
        rep = _report(retention={
            **_report()["retention"],
            "speakers": {"total": 2, "kept": 1, "wiped": ["s2"]},
        })
        g = evaluate(rep, self.cfg)
        self.assertIn("no_wiped_speakers", g["failures"])

    def test_dominant_filter_fails(self):
        g = evaluate(_report(drops={"A5_duration": 60}), self.cfg)
        self.assertIn("single_filter_share", g["failures"])

    def test_clipping_rate_fails(self):
        g = evaluate(_report(drops={"A3_clipping": 5}), self.cfg)
        self.assertIn("clipping_rate", g["failures"])


class TestAutoCalibration(unittest.TestCase):
    def test_auto_then_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            inp = d / "in.jsonl"
            with inp.open("w", encoding="utf-8") as fh:
                for i in range(120):
                    n = 3 + (i % 10)
                    fh.write(json.dumps({
                        "src": " ".join(["monde"] * n),
                        "tgt": " ".join(["mokili"] * n),
                    }, ensure_ascii=False) + "\n")
            cfg_path = d / "preprocess.yaml"
            shutil.copyfile(C.ROOT / "ml" / "preprocess" / "configs" / "preprocess.yaml",
                            cfg_path)

            rc = C.main(["auto", "--lang", "lin", "--input", str(inp),
                         "--out", str(d / "cal"), "--config", str(cfg_path),
                         "--no-audio", "--n-text", "100"])
            self.assertEqual(rc, 0)
            auto = json.loads((d / "cal" / "calibration_auto.json").read_text(encoding="utf-8"))
            self.assertIn("T4_length", auto["seuils"])
            self.assertTrue(auto["seuils"]["T4_length"]["provenance"].startswith("auto_"))
            ev = d / "cal" / "evidence" / "T4_length.json"
            self.assertTrue(ev.exists())
            self.assertIn("data_hash", json.loads(ev.read_text(encoding="utf-8")))

            rc = C.main(["apply", "--lang", "lin", "--out", str(d / "cal"),
                         "--config", str(cfg_path), "--auto"])
            self.assertEqual(rc, 0)
            c = load_config(cfg_path)
            self.assertNotIn("text.T4_length", c.blocked_blocks())
            self.assertNotIn("text.T8_minhash", c.blocked_blocks())
            self.assertTrue(c._block_provenance("T4_length").startswith("auto_"))
            self.assertTrue(c._block_provenance("T8_minhash").startswith("hypothese_"))


class TestPatchEvidence(unittest.TestCase):
    def test_inserts_evidence_after_provenance(self):
        lines = [
            "text:",
            "  T4_length:",
            "    min_words: 1",
            "    max_words: 50",
            "    provenance: null",
            "  T5_length_ratio:",
            "    provenance: null",
        ]
        C._patch_block(lines, "T4_length", {"min_words": 2, "max_words": 40},
                       "auto_p_lin_2026-11-02", "evidence/T4.json")
        txt = "\n".join(lines)
        self.assertIn("min_words: 2", txt)
        self.assertIn("provenance: auto_p_lin_2026-11-02", txt)
        self.assertIn("evidence: evidence/T4.json", txt)
        self.assertLess(txt.index("provenance: auto"), txt.index("evidence: evidence/T4.json"))


if __name__ == "__main__":
    unittest.main()
