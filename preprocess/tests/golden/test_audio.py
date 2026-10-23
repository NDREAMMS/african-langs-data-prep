"""Tests golden — chaîne audio (rééchantillonnage, VAD, découpe, SNR, WER)."""
import tempfile
import unittest
from unittest import mock

import numpy as np

from ml.preprocess import audio_tts as A
from ml.preprocess.common.config import Config
from ml.preprocess.common.journal import Row


class TestResample(unittest.TestCase):
    def test_48k_to_24k(self):
        x = np.sin(2 * np.pi * 440 * np.arange(48000) / 48000).astype(np.float32)
        y = A.resample(x, 48000, 24000)
        self.assertAlmostEqual(len(y), 24000, delta=5)

    def test_16k_to_24k(self):
        x = np.zeros(16000, np.float32)
        y = A.resample(x, 16000, 24000)
        self.assertAlmostEqual(len(y), 24000, delta=5)

    def test_same_rate_noop(self):
        x = np.ones(100, np.float32)
        self.assertTrue(np.array_equal(A.resample(x, 24000, 24000), x))


def _tone(freq: float, n: int, sr: int = 24000, amp: float = 0.5) -> np.ndarray:
    # fréquence NON entière : évite 2π·freq·n ≡ nombre entier de tours (sin≡0).
    return (amp * np.sin(2 * np.pi * freq * np.arange(n) / sr)).astype(np.float32)


class TestVadSegment(unittest.TestCase):
    def test_trim_silence(self):
        sr = 24000
        speech = _tone(220.5, sr)
        x = np.concatenate([np.zeros(sr, np.float32), speech, np.zeros(sr, np.float32)])
        y = A.trim_silence(x, sr, edge_s=0.1)
        self.assertLess(len(y), len(x))
        self.assertGreater(len(y), sr)                       # la parole est conservée

    def test_segment_bounds(self):
        sr = 24000
        x = np.ones(25 * sr, np.float32)
        segs = A.segment(x, sr, max_s=10.0)
        self.assertTrue(all(len(s) <= 10 * sr for s in segs))
        self.assertAlmostEqual(sum(len(s) for s in segs), len(x), delta=sr)


class TestMetrics(unittest.TestCase):
    def test_snr_high_for_clean(self):
        sr = 24000
        rng = np.random.default_rng(0)
        silence = (1e-3 * rng.standard_normal(sr)).astype(np.float32)
        speech = _tone(220.5, sr)
        x = np.concatenate([silence, speech, silence])
        self.assertGreater(A.estimate_snr_db(x, sr), 15.0)

    def test_wer(self):
        self.assertEqual(A.wer("a b c", "a b c"), 0.0)
        self.assertAlmostEqual(A.wer("a b c d", "a b x d"), 0.25)

    def test_clipping(self):
        self.assertGreater(A.true_peak_dbfs(np.ones(100, np.float32)), -1.0)
        self.assertLess(A.true_peak_dbfs(0.1 * np.ones(100, np.float32)), -1.0)


class TestPipeline(unittest.TestCase):
    def test_run_resamples_segments_only(self):
        cfg = Config(raw={
            "meta": {"lang": "lin"},
            "audio": {
                "target_sr": 24000,
                "A4_vad": {"backend": "energy", "edge_silence_s": 0.5},
                "A5_duration": {"min_s": 0.5, "max_s": 10.0, "beyond": "bucket"},
                "A6_rate": {"max_words_per_s": 4.0},
                "A7_dnsmos": {"min": 3.0, "model_path": None},
                "A8_snr": {"min_db": 15.0},
                "A9_asr_wer": {"max_wer": 0.30, "model_path": None},
                "A3_loudness": {"max_true_peak_dbfs": -1.0},
                "A12_mel": {"enabled": False},
            },
        }, path="/tmp/preprocess.yaml", hash="test")

        row = Row(row_id="row1", lang="lin", source="bibletts", speaker="spk", domain="bible",
                  text="bonjour tout le monde")
        item = A.AudioItem(row=row, samples=np.ones(60000, np.float32), sr=48000, path="/tmp/test.wav")

        calls = []
        with mock.patch.object(A, "_gather_stream", return_value=[item]), \
             mock.patch.object(A, "load_audio", return_value=item), \
             mock.patch.object(A, "trim_silence", side_effect=lambda x, sr, *a, **k: x), \
             mock.patch.object(A, "segment", return_value=[np.ones(4000, np.float32), np.ones(4000, np.float32)]), \
             mock.patch.object(A, "split_tokens_by_duration", return_value=["bonjour", "tout le monde"]), \
             mock.patch.object(A, "true_peak_dbfs", return_value=-3.0), \
             mock.patch.object(A, "estimate_snr_db", return_value=30.0), \
             mock.patch.object(A, "resample", side_effect=lambda x, sr_in, sr_out, **k: (calls.append((len(x), sr_in, sr_out)) or x.astype(np.float32))), \
             mock.patch.object(A, "_write_mel", return_value=None):
            with tempfile.TemporaryDirectory() as tmp:
                A.run(cfg, tmp, sources=["bibletts"], limit=None)

        self.assertEqual(calls, [(4000, 48000, 24000), (4000, 48000, 24000)])


if __name__ == "__main__":
    unittest.main()
