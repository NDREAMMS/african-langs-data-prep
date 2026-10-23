"""Normalisation Unicode et texte (§2.5, §4 T3, §6 G1).

Principe §2.5 : stockage en NFC, analyse en NFD.
  - NFC : une seule forme canonique par chaîne (unicité, hash stable) ;
  - NFD : les marques de ton se séparent des voyelles — indispensable au lexique tonal (D8).
"""
from __future__ import annotations

import html
import re
import unicodedata

_WS = re.compile(r"\s+")
_HTML_TAG = re.compile(r"<[^>]+>")
_DIGIT = re.compile(r"\d+")


def to_nfc(text: str) -> str:
    """Forme de stockage canonique."""
    return unicodedata.normalize("NFC", text)


def to_nfd(text: str) -> str:
    """Forme d'analyse (segmentation des diacritiques / tons)."""
    return unicodedata.normalize("NFD", text)


def strip_tones(text: str) -> str:
    """Retire les marques de ton (Mn non combinées ailleurs) — clé d'unicité lexicale (G5)."""
    return "".join(c for c in to_nfd(text) if not unicodedata.combining(c))


def clean_text(text: str) -> str:
    """Nettoyage texte de base : entités HTML, balises, espaces multiples, NFC."""
    text = html.unescape(text)
    text = _HTML_TAG.sub(" ", text)
    text = text.replace("\u00a0", " ")
    text = _WS.sub(" ", text).strip()
    return to_nfc(text)


def tokenize(text: str) -> list[str]:
    """Tokenisation simple sur les blancs (suffisante pour les compteurs de rétention)."""
    return [t for t in _WS.split(text.strip()) if t]


# ---------------------------------------------------------------------------
# Numéraux (§4 T3) — table par langue, partagée texte/audio.
# ---------------------------------------------------------------------------
def _number_to_words(n: int, table: dict) -> str | None:
    units: dict = table.get("units", {})
    tens: dict = table.get("tens", {})
    scales: dict = table.get("scales", {})
    connector: str = table.get("connector", " ")
    if n in units:
        return units[n]
    if n in tens:
        return tens[n]
    if 0 <= n < 100:
        t, u = divmod(n, 10)
        if t * 10 in tens and u in units:
            return f"{tens[t * 10]} {connector} {units[u]}"
    if n in scales:
        return scales[n]
    for scale in sorted(scales, reverse=True):
        if n > scale:
            q, r = divmod(n, scale)
            head = _number_to_words(q, table)
            tail = _number_to_words(r, table) if r else None
            if head and (tail or r == 0):
                return f"{head} {scales[scale]}" + (f" {connector} {tail}" if tail else "")
    return None


def _spell_digits(n: int, units: dict) -> str:
    return " ".join(units.get(int(d), d) for d in str(n))


def normalize_numerals(text: str, table: dict) -> str:
    """Remplace les suites de chiffres par leur forme en mots.

    Repli (fallback) : `digits` (épeler chiffre à chiffre) ou `keep` (laisser tel quel).
    """
    units = table.get("units", {})
    fallback = table.get("fallback", "digits")

    def repl(m: re.Match) -> str:
        n = int(m.group(0))
        words = _number_to_words(n, table)
        if words is not None:
            return words
        if fallback == "digits":
            return _spell_digits(n, units)
        return m.group(0)

    return _DIGIT.sub(repl, text)
