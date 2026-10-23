"""Dédoublonnage : exact (T2) puis approximatif MinHash LSH (T8)."""
from __future__ import annotations

import hashlib


def exact_key(*parts: str) -> str:
    """sha1 des champs joints — clé d'unicité exacte (T2)."""
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def stable_hash(text: str, salt: str = "") -> int:
    """Hash stable pour le découpage train/dev/test (T11) et l'anti-fuite (A10/T10)."""
    return int(hashlib.sha1((salt + text).encode("utf-8")).hexdigest()[:16], 16)


def _shingles(text: str, n: int) -> set[str]:
    toks = text.split()
    if len(toks) < n:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}


class MinHashDedup:
    """Dédoublonnage par similarité de n-grammes (MinHash LSH, datasketch).

    Utilisé pour T8 (texte) et A10 (anti-fuite) le cas échéant.
    """

    def __init__(self, ngram: int = 5, threshold: float = 0.85, num_perm: int = 128):
        from datasketch import MinHash, MinHashLSH  # import paresseux

        self._MinHash = MinHash
        self._ngram = ngram
        self._lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self._num_perm = num_perm

    def _minhash(self, text: str):
        m = self._MinHash(num_perm=self._num_perm)
        for sh in _shingles(text, self._ngram):
            m.update(sh.encode("utf-8"))
        return m

    def is_duplicate(self, row_id: str, text: str) -> bool:
        """Renvoie True si `text` est proche d'un texte déjà vu ; sinon l'indexe."""
        m = self._minhash(text)
        if self._lsh.query(m):
            return True
        self._lsh.insert(row_id, m)
        return False
