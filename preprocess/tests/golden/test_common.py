"""Tests golden — socle (unicode, numéraux, journal, dédoublonnage, config)."""
import unittest

from ml.preprocess.common import unicode_norm as U
from ml.preprocess.common.config import load_config, load_numerals
from ml.preprocess.common.dedup import MinHashDedup, exact_key
from ml.preprocess.common.journal import Journal, Row


class TestUnicode(unittest.TestCase):
    def test_nfc_stable(self):
        self.assertEqual(U.to_nfc("é"), U.to_nfc("e\u0301"))

    def test_nfd_separates_tone(self):
        # nfd : la marque se sépare de la lettre (pré-requis du lexique tonal, D8)
        self.assertEqual(len(U.to_nfd("ó")), 2)

    def test_strip_tones(self):
        self.assertEqual(U.strip_tones("kokóma"), "kokoma")

    def test_clean_text(self):
        self.assertEqual(U.clean_text("  a&nbsp; b <b>x</b> "), "a b x")


class TestNumerals(unittest.TestCase):
    def setUp(self):
        self.tbl = load_numerals()

    def test_units(self):
        self.assertEqual(U.normalize_numerals("mibale 2", self.tbl), "mibale mibale")

    def test_tens_units(self):
        self.assertEqual(U.normalize_numerals("22", self.tbl), "ntuku mibale na mibale")


class TestJournal(unittest.TestCase):
    def test_retention_and_wiped(self):
        jr = Journal("tts", "lin")
        r1 = Row("1", "lin", "waxal", speaker="s1")
        r2 = Row("2", "lin", "waxal", speaker="s2")
        jr.see_input(r1, ["a", "b"])
        jr.see_input(r2, ["b", "c"])
        jr.see_output(r1, ["a", "b"])
        jr.drop(r2, "A8_snr", "bruit")
        rep = jr.retention()
        self.assertEqual(rep["speakers"]["kept"], 1)
        self.assertEqual(rep["speakers"]["wiped"], ["s2"])
        self.assertAlmostEqual(rep["vocab_unique"], 0.667, places=2)

    def test_drop_frac(self):
        jr = Journal("tts", "lin")
        for i in range(10):
            jr.see_input(Row(str(i), "lin", "waxal"))
        for i in range(6):
            jr.drop(Row(str(i), "lin", "waxal"), "A5_duration", "durée")
        self.assertAlmostEqual(jr.drop_frac("A5_duration"), 0.6, places=2)


class TestDedup(unittest.TestCase):
    def test_exact_key_stable(self):
        self.assertEqual(exact_key("a", "b"), exact_key("a", "b"))
        self.assertNotEqual(exact_key("a", "b"), exact_key("b", "a"))

    def test_minhash(self):
        d = MinHashDedup(ngram=3, threshold=0.8)
        s = "mokili mobimba ezali na bomoi ya bato nyonso"
        self.assertFalse(d.is_duplicate("x", s))
        self.assertTrue(d.is_duplicate("y", s))              # identique
        self.assertFalse(d.is_duplicate("z", "ndaku oyo ezali na bosoto"))


class TestConfig(unittest.TestCase):
    def test_hash_stable_and_uncalibrated_gate(self):
        c1, c2 = load_config(), load_config()
        self.assertEqual(c1.hash, c2.hash)
        self.assertFalse(c1.publishable)                     # seuils non calibrés
        self.assertTrue(len(c1.uncalibrated()) > 0)


if __name__ == "__main__":
    unittest.main()
