"""Lecture USFM → versets indexés par (livre, chapitre, verset).

Pourquoi USFM : les sources bibliques alignables (Open.Bible / eBible) partagent
la même structure `\\c`/`\\v` et la même versification standard, ce qui donne un
alignement verset par verset **exact** — sans traduction automatique, donc sans
bruit d'alignement. C'est le socle propre du corpus français↔lingala.

Le texte est *nettoyé* du balisage : notes (`\\f…\\f*`, `\\x…\\x*`), mots Strong
(`\\w mot|strong="H…"\\w*`), titres de section, etc.
"""
from __future__ import annotations

import re
from pathlib import Path

# Marqueurs dont le contenu doit DISPARAÎTRE complètement (notes, références).
_NOTE_MARKERS = ("f", "x", "rq", "fig")

# Marqueurs de paragraphe/poésie : une ligne qui commence ainsi *prolonge* le verset.
_CONT = {
    "p", "m", "mi", "nb", "pc", "pc", "pi", "pi1", "pi2", "pi3",
    "q", "q1", "q2", "q3", "q4", "qm", "qm1", "qm2", "qm3",
    "li", "li1", "li2", "li3", "li4", "lf", "lf1", "lf2", "lim", "lim1", "lim2",
    "ph", "ph1", "ph2", "ph3", "pi", "mi",
}

_ATTR = re.compile(r"\|[^\\]*(?=\\|$)")
_CLOSE = re.compile(r"\\\+?[a-z0-9]+\*")
_OPEN = re.compile(r"\\\+?[a-z0-9]+\b")
_WS = re.compile(r"\s+")
_V = re.compile(r"^\\v\s+(\d+)(?:[-–]\d+)?\s?(.*)$")
_C = re.compile(r"^\\c\s+(\d+)")
_ID = re.compile(r"\\id\s+([1-3]?[A-Z]{2,3})")
_ANY_MARKER = re.compile(r"^\\([+a-z0-9]+)\s?(.*)$")

# Continuités verset : paragraphes et poésie ; le reste (titres \s, \r, \ms…) est ignoré.
_BOOK_NAMES = {
    "GEN": "Genèse", "EXO": "Exode", "LEV": "Lévitique", "NUM": "Nombres", "DEU": "Deutéronome",
    "JOS": "Josué", "JDG": "Juges", "RUT": "Ruth", "1SA": "1 Samuel", "2SA": "2 Samuel",
    "1KI": "1 Rois", "2KI": "2 Rois", "1CH": "1 Chroniques", "2CH": "2 Chroniques",
    "EZR": "Esdras", "NEH": "Néhémie", "EST": "Esther", "JOB": "Job", "PSA": "Psaumes",
    "PRO": "Proverbes", "ECC": "Ecclésiaste", "SNG": "Cantique", "ISA": "Ésaïe",
    "JER": "Jérémie", "LAM": "Lamentations", "EZK": "Ézéchiel", "DAN": "Daniel",
    "HOS": "Osée", "JOL": "Joël", "AMO": "Amos", "OBA": "Abdias", "JON": "Jonas",
    "MIC": "Michée", "NAM": "Nahum", "HAB": "Habacuc", "ZEP": "Sophonie",
    "HAG": "Aggée", "ZEC": "Zacharie", "MAL": "Malachie", "MAT": "Matthieu",
    "MRK": "Marc", "LUK": "Luc", "JHN": "Jean", "ACT": "Actes", "ROM": "Romains",
    "1CO": "1 Corinthiens", "2CO": "2 Corinthiens", "GAL": "Galates", "EPH": "Éphésiens",
    "PHP": "Philippiens", "COL": "Colossiens", "1TH": "1 Thessaloniciens",
    "2TH": "2 Thessaloniciens", "1TI": "1 Timothée", "2TI": "2 Timothée",
    "TIT": "Tite", "PHM": "Philémon", "HEB": "Hébreux", "JAS": "Jacques",
    "1PE": "1 Pierre", "2PE": "2 Pierre", "1JN": "1 Jean", "2JN": "2 Jean",
    "3JN": "3 Jean", "JUD": "Jude", "REV": "Apocalypse",
}


def book_name(code: str) -> str:
    return _BOOK_NAMES.get(code, code)


def _strip_spans(s: str) -> str:
    for m in ("f", "x", "rq", "fig"):
        s = re.sub(rf"\\{m}\b.*?\\{m}\*", " ", s, flags=re.S)
    return s


def clean_verse(s: str) -> str:
    """Retire tout le balisage USFM d'un fragment de verset."""
    s = _strip_spans(s)
    s = _ATTR.sub("", s)        # attributs |strong="…" etc.
    s = _CLOSE.sub("", s)       # marqueurs fermants \w* \add* …
    s = _OPEN.sub(" ", s)       # marqueurs ouvrants inline \w \add \nd …
    s = s.replace("~", "\u00a0")
    return _WS.sub(" ", s).strip()


def parse_file(path: str | Path) -> tuple[str | None, dict[tuple[str, int, int], str]]:
    """Parse un fichier USFM → (code livre, {(livre, chapitre, verset): texte})."""
    text = Path(path).read_text(encoding="utf-8-sig")
    mid = _ID.search(text)
    book = mid.group(1) if mid else None

    verses: dict[tuple[str, int, int], str] = {}
    chapter = 0
    cur_v: int | None = None
    buf: list[str] = []

    def flush():
        nonlocal buf, cur_v
        if cur_v is not None and book:
            txt = clean_verse(" ".join(buf))
            if txt:
                verses[(book, chapter, cur_v)] = txt
        buf = []

    for line in text.splitlines():
        mc = _C.match(line)
        if mc:
            flush()
            chapter = int(mc.group(1))
            cur_v = None
            continue
        mv = _V.match(line)
        if mv:
            flush()
            cur_v = int(mv.group(1))
            buf = [mv.group(2)]
            continue
        am = _ANY_MARKER.match(line)
        if am:
            if cur_v is not None and am.group(1) in _CONT:
                buf.append(am.group(2))
            continue
        if cur_v is not None and line.strip():
            buf.append(line)
    flush()
    return book, verses


def load_dir(directory: str | Path) -> dict[tuple[str, int, int], str]:
    """Charge tous les `.usfm` d'un dossier en un index verset unique."""
    out: dict[tuple[str, int, int], str] = {}
    for p in sorted(Path(directory).glob("*.usfm")):
        _book, verses = parse_file(p)
        out.update(verses)
    return out
