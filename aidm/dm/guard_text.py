"""Text helpers of the prose guard: tokens, phrase hits with word boundaries, negation windows.

Matching is always on word boundaries, so "unbroken" never matches "broken" and "Miranda"
never matches "Mira". Possessives ("Mira's") and simple plurals ("goblins") reduce to their base.
Every typographic apostrophe counts as the plain one (`plain`, M20.1: a hero stored as
"El’Skalfidar" was flagged in every model sentence that named him), on the prose side and on the
name side alike.

Public API: `APOSTROPHES`, `plain(text)`, `Token(text, start, end, initial)`, `tokenize(text)`,
`base_word(word)`, `singular_forms(word)`, `find_phrases(text, phrases)` (cached patterns),
`is_negated(tokens, index, negations, span)`.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache

from aidm.dm.sentence_chunker import ABBREVIATIONS

APOSTROPHES = "’‘ʼ`´′"
_PLAIN = str.maketrans(dict.fromkeys(APOSTROPHES, "'"))
_TOKEN = re.compile(rf"[A-Za-z]+(?:['{APOSTROPHES}][A-Za-z]+)*")
_STARTS = frozenset('.!?"“‘(:\n')
_STEM = re.compile(r"([A-Za-z][A-Za-z.]*?)\.$")


def plain(text: str) -> str:
    """The text with every typographic apostrophe as the ASCII one (same length)."""
    return text.translate(_PLAIN)


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    initial: bool

    @property
    def lower(self) -> str:
        return plain(self.text).casefold()

    @property
    def capitalised(self) -> bool:
        return self.text[0].isupper()


def _is_initial(text: str, start: int) -> bool:
    before = text[:start].rstrip(" \t")
    if not before:
        return True
    if before[-1] == ".":
        stem = _STEM.search(before)
        word = stem.group(1) if stem is not None else ""
        if word.casefold() in ABBREVIATIONS or (len(word) == 1 and word.isupper()):
            return False
    return before[-1] in _STARTS


def tokenize(text: str) -> list[Token]:
    return [
        Token(m.group(0), m.start(), m.end(), _is_initial(text, m.start()))
        for m in _TOKEN.finditer(text)
    ]


def base_word(word: str) -> str:
    clean = plain(word)
    if clean.lower().endswith("'s"):
        return clean[:-2]
    return clean.rstrip("'")


def singular_forms(word: str) -> tuple[str, ...]:
    low = word.casefold()
    forms = [low]
    if low.endswith("ies") and len(low) > 4:
        forms.append(low[:-3] + "y")
    if low.endswith("es") and len(low) > 3:
        forms.append(low[:-2])
    if low.endswith("s") and len(low) > 2:
        forms.append(low[:-1])
    if low.endswith("ves"):
        forms.append(low[:-3] + "f")
    return tuple(forms)


@cache
def _compiled(phrases: frozenset[str]) -> re.Pattern[str]:
    ordered = sorted(phrases, key=lambda p: (-len(p), p))
    body = "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in ordered)
    return re.compile(rf"(?<![A-Za-z'])(?:{body})(?![A-Za-z])", re.IGNORECASE)


def find_phrases(text: str, phrases: Iterable[str]) -> list[re.Match[str]]:
    words = frozenset(plain(p) for p in phrases)
    if not words:
        return []
    return list(_compiled(words).finditer(plain(text)))


def is_negated(tokens: list[Token], index: int, negations: frozenset[str], span: int = 3) -> bool:
    for token in tokens[max(0, index - span) : index]:
        low = token.lower
        if low in negations or low.endswith("n't"):
            return True
    return False
