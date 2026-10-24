"""Typed-intent phrase table: data/bg3/intent_phrases.json (M30.0b, one intent router; data over
code). The router (`aidm.dm.intent_match`) reads it; nothing here holds game logic.

Shape:
- `slots`: regex fragments by name. A row pattern writes `{name}` for the fragment and
  `{name:group}` for the fragment as the named object slot `group`;
- `lexicon`: lowercase word sets by name (verbs, skill words, vetoes);
- `patterns`: named regex templates (vetoes, readings, shared patterns);
- `scopes`: the routing scopes (`explore` out of a fight, `fight`, `ask`): the base reading of
  the sentence and the named conditions the whole scope needs;
- `rows`: one phrase row each: the scopes it serves, its intent family and resolver, an
  explicit `precedence` (unique; the lowest that resolves wins, never file order), the readings
  it tries, its patterns (`{verbs}` / `{verbs:group}` the pattern's or row's verb alternatives,
  which are regex), `has_words` (a word of every named set), `unless` (a named set or pattern
  that vetoes the row), `when` (named state conditions), `on_match` (`next`, `stop_family`,
  `stop`: what a match that resolves to nothing does) and `params` for the resolver.

Public API: `IntentPhrases`, `PhraseRow`, `PhrasePattern`, `PhraseScope`, `PLACEHOLDER`,
`load_intent_phrases(path=None)`, `intent_phrases()` (cached).
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

DEFAULT_INTENT_PHRASES = (
    Path(__file__).resolve().parents[2] / "data" / "bg3" / "intent_phrases.json"
)
PLACEHOLDER = re.compile(r"\{([a-z_]+)(?::([a-z_0-9]+))?\}")

type Reading = Literal[
    "base",
    "comma_head",
    "and_head",
    "clause_head",
    "head_or_whole",
    "aim",
    "item_tail",
    "no_pick_up",
    "plain",
    "strip",
    "named_cut",
    "own",
]


class PhrasePattern(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    re: str = ""
    ref: str = ""  # a named pattern of the table instead of `re`
    verbs: tuple[str, ...] = ()
    params: dict[str, str | bool] = {}


class PhraseRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    scopes: tuple[str, ...]
    family: str
    precedence: int
    resolver: str
    readings: tuple[Reading, ...] = ("base",)
    match: Literal["full", "search"] = "full"
    patterns: tuple[PhrasePattern, ...] = ()
    verbs: tuple[str, ...] = ()
    tokens: Literal["letters", "alnum", "word"] = "word"
    has_words: tuple[str, ...] = ()
    unless: tuple[str, ...] = ()
    when: tuple[str, ...] = ()
    on_match: Literal["next", "stop_family", "stop"] = "next"
    scan: Literal["first", "each"] = "first"
    params: dict[str, str | bool] = {}
    note: str = ""


class PhraseScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base: Literal["own", "normal", "as_is"]
    when: tuple[str, ...] = ()


class IntentPhrases(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = ""
    slots: dict[str, str]
    lexicon: dict[str, frozenset[str]]
    patterns: dict[str, str]
    scopes: dict[str, PhraseScope]
    rows: tuple[PhraseRow, ...]

    @model_validator(mode="after")
    def _check(self) -> IntentPhrases:
        ids = [r.id for r in self.rows]
        if len(set(ids)) != len(ids):
            raise ValueError("intent phrase row ids must be unique")
        ranks = [r.precedence for r in self.rows]
        if len(set(ranks)) != len(ranks):
            raise ValueError("intent phrase precedence must be unique (never file order)")
        if set(self.lexicon) & set(self.patterns):
            raise ValueError("a lexicon set and a pattern share a name")
        for name, words in self.lexicon.items():
            if any(w != w.lower() or not w.strip() for w in words):
                raise ValueError(f"lexicon {name!r} must be lowercase words")
        for row in self.rows:
            self._check_row(row)
        return self

    def _check_row(self, row: PhraseRow) -> None:
        if not set(row.scopes) <= set(self.scopes):
            raise ValueError(f"row {row.id!r} names an unknown scope")
        if not set(row.has_words) <= set(self.lexicon):
            raise ValueError(f"row {row.id!r} has_words names an unknown lexicon set")
        if not set(row.unless) <= set(self.lexicon) | set(self.patterns):
            raise ValueError(f"row {row.id!r} unless names an unknown set or pattern")
        for pattern in row.patterns:
            if bool(pattern.re) == bool(pattern.ref) or (
                pattern.ref and pattern.ref not in self.patterns
            ):
                raise ValueError(f"row {row.id!r}: a pattern needs one known `re` or `ref`")
            for name, _ in PLACEHOLDER.findall(pattern.re):
                if name != "verbs" and name not in self.slots:
                    raise ValueError(f"row {row.id!r} names an unknown slot {name!r}")


def load_intent_phrases(path: Path | None = None) -> IntentPhrases:
    raw = json.loads((path or DEFAULT_INTENT_PHRASES).read_text(encoding="utf-8"))
    return IntentPhrases.model_validate(raw)


@functools.cache
def intent_phrases() -> IntentPhrases:
    return load_intent_phrases()
