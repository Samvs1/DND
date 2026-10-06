"""Incremental sentence chunker for streamed narration (SPEC 6.1 step 3, 11: chunked for TTS).

Text arrives in arbitrary pieces; `SentenceChunker.feed` returns every sentence that is complete
so far and keeps the rest buffered, `flush` returns the remainder at the end of the stream.

A boundary is terminal punctuation (`.`, `!`, `?`, an ellipsis), optional closing quotes or
brackets, whitespace, and then a next character that is NOT a lowercase letter (so `"Run!" she
yelled` and `He waits... then nods` stay one sentence). A boundary is only decided once that
next character has arrived, so a sentence is never cut early. Not boundaries: a period after a
known abbreviation ("Mr.", "Dr.", "St.", "e.g.") or a single capital initial ("J."), and a
decimal number ("3.5" has no whitespace after the dot). A blank line is always a boundary.

Public API: `SentenceChunker` (`feed(text) -> list[str]`, `flush() -> list[str]`),
`split_sentences(text) -> list[str]`, `strip_marks(text) -> str`,
`strip_markdown(sentence) -> str`, `ABBREVIATIONS`.
"""

import re

ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "st",
        "mt",
        "jr",
        "sr",
        "vs",
        "prof",
        "capt",
        "sgt",
        "lt",
        "col",
        "gen",
        "rev",
        "etc",
        "e.g",
        "i.e",
        "approx",
    }
)

_BOUNDARY = re.compile(
    r"(?P<punct>[.!?…]+)(?P<close>[\"'”’)\]]*)(?P<space>\s+)(?=(?P<next>\S))"
    r"|(?P<para>\n[ \t]*\n\s*)(?=\S)"
)
_WORD_BEFORE = re.compile(r"([A-Za-z.]+)$")


def _is_abbreviation(text_before: str) -> bool:
    match = _WORD_BEFORE.search(text_before)
    if match is None:
        return False
    word = match.group(1).strip(".")
    if len(word) == 1 and word.isupper():
        return True
    return word.casefold() in ABBREVIATIONS


def _is_boundary(buf: str, match: re.Match[str]) -> bool:
    if match.group("para") is not None:
        return True
    if match.group("next").islower():
        return False
    punct = match.group("punct")
    return not (punct == "." and _is_abbreviation(buf[: match.start("punct")]))


class SentenceChunker:
    def __init__(self) -> None:
        self._buf = ""

    def feed(self, text: str) -> list[str]:
        self._buf += text
        out: list[str] = []
        start = 0
        while True:
            match = next(
                (m for m in _BOUNDARY.finditer(self._buf, start) if _is_boundary(self._buf, m)),
                None,
            )
            if match is None:
                break
            cut = match.end("close") if match.group("para") is None else match.start("para")
            sentence = self._buf[:cut].strip()
            self._buf = self._buf[match.end() :]
            start = 0
            if sentence:
                out.append(sentence)
        return out

    def flush(self) -> list[str]:
        rest = self._buf.strip()
        self._buf = ""
        return [rest] if rest else []


def split_sentences(text: str) -> list[str]:
    chunker = SentenceChunker()
    return [*chunker.feed(text), *chunker.flush()]


_HEADING = re.compile(r"^\s*(?:#{1,6}\s+|>\s+|[-*+]\s+(?=\S))")
_MARKS = re.compile(r"`+|\*+|_{2,}|~{2,}")


def strip_marks(text: str) -> str:
    """Drop inline markdown marks from a streamed piece: backticks, asterisks, `__`, `~~`."""
    return _MARKS.sub("", text)


def strip_markdown(sentence: str) -> str:
    """Plain prose for players and TTS (QA-13): inline marks plus a leading heading, quote or
    list marker removed, whitespace collapsed."""
    plain = strip_marks(_HEADING.sub("", sentence))
    return " ".join(plain.split())
