"""Chaîne G2P (lexique tonal) — G1..G7 (§6). BLOQUÉE.

Dépendance : licence d'export du lexique bambara (An ka taa / Corbama) non confirmée (D14).
Le G2P lingala n'est pas bloqué par la licence mais par la construction du lexique tonal
(grammaires lingala, D8) — hors périmètre tant que l'étape 0 n'est pas faite.

Interface prévue (D10) : {"graphemes","phonemes","tones","syllables","lang"}.
Pour `tone_model: none` (ex. wolof par défaut), le champ `tones` est vide (jamais rempli
par convention de complaisance, §6).
"""
from __future__ import annotations


class G2PBlocked(RuntimeError):
    pass


def run(*_args, **_kwargs):
    raise G2PBlocked(
        "Chaîne G2P bloquée : licence d'export du lexique à confirmer (D14). "
        "Voir §6 et §11 du document de prétraitement."
    )
