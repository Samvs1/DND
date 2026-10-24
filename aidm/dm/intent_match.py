"""The one matcher of typed intents (M30.0b): it reads the phrase table
(`aidm.data.intent_phrases`) and nothing else decides which intent a sentence is.

`route(state, actor_id, text, resolvers, scope=..., families=..., base=...)`:
1. the scope's conditions must hold (`aidm.dm.intent_conditions`);
2. the rows of the scope (or of the named families) run in `precedence` order, lowest first;
3. a row tries its readings in order (dropping empty and repeated ones); on a reading a
   pattern must match (`full` or `search`) and the reading must hold a word of every
   `has_words` set; `unless` vetoes the row when its set or pattern hits the row's FIRST
   reading (the whole sentence as the row sees it);
4. on the first match the row's `when` conditions are checked once; then its resolver (the
   state lookups of that intent) gets the match as a `Found`. With `scan: first` the first
   pattern that matches a reading decides that reading, with `each` every matching pattern
   is resolved in turn. The first result is the intent;
5. a row that matched but gave nothing: `next` goes on, `stop_family` skips the family's
   later rows, `stop` ends the routing with None.

Readings (the regexes they use are table patterns): `base` (the entry's base: `own` the
hero's own reading of the normalised sentence, `normal` normalised, `as_is` the text given),
`comma_head`, `and_head`, `clause_head` (head of `sentence.split_clause`, the rest kept as
`Found.rest`), `head_or_whole`, `aim` (a purpose tail cut when the sentence has one act),
`item_tail` ("instead ..." cut), `no_pick_up`, and from the raw text `plain`, `strip`,
`named_cut` (the hero's name cut, verb kept) and `own`.

Public API: `Found`, `Resolver`, `route(...)`, `text_match(row_ids, text)`, `expand(row, pattern)`.
"""

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cache

from aidm.data.intent_phrases import (
    PLACEHOLDER,
    IntentPhrases,
    PhrasePattern,
    PhraseRow,
    intent_phrases,
)
from aidm.dm.intent_conditions import CONDITIONS
from aidm.dm.sentence import normalise, own_reading, split_clause
from aidm.models.state import GameState


@dataclass(frozen=True)
class Found:
    state: GameState
    actor_id: str
    text: str
    rest: str | None
    groups: Mapping[str, str | None]
    params: Mapping[str, str | bool]
    words: frozenset[str]

    def group(self, name: str) -> str | None:
        return self.groups.get(name)


type Resolver = Callable[[Found], object | None]
type _Read = tuple[str, str | None]

_TOKENS = {
    "letters": lambda t: re.findall(r"[a-z]+", t),
    "alnum": lambda t: re.findall(r"[a-z0-9]+", t.lower().replace("-", " ")),
    "word": lambda t: re.findall(r"[a-z0-9']+", t.lower().replace("-", " ")),
}


def expand(row: PhraseRow, pattern: PhrasePattern, table: IntentPhrases | None = None) -> str:
    """The regex of one row pattern: slots and verbs filled in."""
    table = table or intent_phrases()
    if pattern.ref:
        return table.patterns[pattern.ref]
    verbs = "|".join(pattern.verbs or row.verbs)

    def fill(m: re.Match[str]) -> str:
        body = verbs if m[1] == "verbs" else table.slots[m[1]]
        return f"(?P<{m[2]}>{body})" if m[2] else f"(?:{body})" if m[1] == "verbs" else body

    return PLACEHOLDER.sub(fill, pattern.re)


_COMPILED: dict[int, tuple[IntentPhrases, dict[str, tuple[re.Pattern[str], ...]]]] = {}


def _compiled(table: IntentPhrases, row_id: str) -> tuple[re.Pattern[str], ...]:
    """The row's compiled patterns (cached per table object; the table is kept alive)."""
    held = _COMPILED.setdefault(id(table), (table, {}))[1]
    if row_id not in held:
        row = next(r for r in table.rows if r.id == row_id)
        held[row_id] = tuple(re.compile(expand(row, p, table)) for p in row.patterns)
    return held[row_id]


@cache
def _regex(source: str) -> re.Pattern[str]:
    return re.compile(source)


def _named(table: IntentPhrases, name: str) -> re.Pattern[str]:
    return _regex(table.patterns[name])


def _flat(raw: str) -> str:
    return " ".join(raw.lower().replace("’", "'").split())


def _name_cut(name: str, text: str) -> str:
    low = name.lower()
    for prefix in (low, low.split()[0] if low else ""):
        if prefix and text.startswith(f"{prefix} "):
            return text[len(prefix) + 1 :]
    return text


@dataclass(frozen=True)
class _Texts:
    raw: str
    base: str
    name: str
    table: IntentPhrases

    def sub(self, pattern: str, text: str, by: str = "") -> str:
        return _named(self.table, pattern).sub(by, text)


def _reading(texts: _Texts, name: str) -> _Read | None:
    base = texts.base
    match name:
        case "base":
            return base, None
        case "comma_head":
            return base.split(",")[0].strip(), None
        case "and_head":
            return base.split(" and ")[0].strip(), None
        case "clause_head" | "head_or_whole":
            cut = split_clause(base)
            return cut if cut is not None else (None if name == "clause_head" else (base, None))
        case "aim":
            return (texts.sub("purpose", base) if split_clause(base) is None else base), None
        case "item_tail":
            return texts.sub("item_tail", base).strip(), None
        case "no_pick_up":
            return texts.sub("pick_up", base.lower(), " "), None
        case "plain":
            return _flat(texts.raw).rstrip(".!?").strip(), None
        case "strip":
            return _flat(texts.raw).strip(" .!?"), None
        case "named_cut":
            return _name_cut(texts.name, _flat(texts.raw).strip(" .!?")), None
        case _:
            return own_reading(texts.name, normalise(texts.raw)), None


def _readings(row: PhraseRow, texts: _Texts) -> list[_Read]:
    seen: dict[str, str | None] = {}
    for name in row.readings:
        read = _reading(texts, name)
        if read is not None and read[0] and read[0] not in seen:
            seen[read[0]] = read[1]
    return list(seen.items())


def _hits(table: IntentPhrases, name: str, text: str, words: frozenset[str]) -> bool:
    if name in table.lexicon:
        return bool(words & table.lexicon[name])
    return _named(table, name).search(text) is not None


@dataclass(frozen=True)
class _Ctx:
    state: GameState
    actor_id: str
    texts: _Texts
    resolvers: Mapping[str, Resolver]


def _matches(row: PhraseRow, ctx: _Ctx, text: str) -> list[tuple[int, re.Match[str] | None]]:
    """The patterns of the row that match the reading, in order (one empty hit for a row with
    no pattern)."""
    if not row.patterns:
        return [(-1, None)]
    hits: list[tuple[int, re.Match[str] | None]] = []
    for i, regex in enumerate(_compiled(ctx.texts.table, row.id)):
        m = regex.fullmatch(text) if row.match == "full" else regex.search(text)
        if m is not None:
            hits.append((i, m))
    return hits


def _found(row: PhraseRow, ctx: _Ctx, read: _Read, hit: tuple[int, re.Match[str] | None]) -> Found:
    index, m = hit
    params = dict(row.params) | (dict(row.patterns[index].params) if index >= 0 else {})
    words = frozenset(_TOKENS[row.tokens](read[0]))
    groups = m.groupdict() if m is not None else {}
    return Found(ctx.state, ctx.actor_id, read[0], read[1], groups, params, words)


def _try_row(row: PhraseRow, ctx: _Ctx) -> tuple[bool, object | None]:
    """(matched, intent) for one row."""
    readings = _readings(row, ctx.texts)
    if not readings:
        return False, None
    table = ctx.texts.table
    first_words = frozenset(_TOKENS[row.tokens](readings[0][0]))
    if any(_hits(table, n, readings[0][0], first_words) for n in row.unless):
        return False, None
    matched = False
    for read in readings:
        words = frozenset(_TOKENS[row.tokens](read[0]))
        if not all(words & table.lexicon[n] for n in row.has_words):
            continue
        for hit in _matches(row, ctx, read[0]):
            found = _found(row, ctx, read, hit)
            if not matched and not all(CONDITIONS[c](found) for c in row.when):
                return True, None
            matched = True
            result = ctx.resolvers[row.resolver](found)
            if result is not None:
                return True, result
            if row.scan == "first":
                break
    return matched, None


def _base(kind: str, raw: str, name: str) -> str:
    if kind == "as_is":
        return raw
    clean = normalise(raw)
    return own_reading(name, clean) if kind == "own" else clean


def _rows(table: IntentPhrases, scope: str | None, families: Iterable[str]) -> list[PhraseRow]:
    wanted = frozenset(families)
    rows = [r for r in table.rows if (scope in r.scopes if scope else r.family in wanted)]
    return sorted(rows, key=lambda r: r.precedence)


def route(
    state: GameState,
    actor_id: str,
    text: str,
    resolvers: Mapping[str, Resolver],
    *,
    scope: str | None = None,
    families: Iterable[str] = (),
    base: str = "own",
    table: IntentPhrases | None = None,
) -> object | None:
    table = table or intent_phrases()
    actor = state.creatures.get(actor_id)
    name = actor.name if actor is not None else ""
    if scope is not None:
        config = table.scopes[scope]
        base = config.base
        bare = Found(state, actor_id, text, None, {}, {}, frozenset())
        if not all(CONDITIONS[c](bare) for c in config.when):
            return None
    texts = _Texts(text, _base(base, text, name), name, table)
    if not texts.base:
        return None
    ctx = _Ctx(state, actor_id, texts, resolvers)
    stopped: set[str] = set()
    for row in _rows(table, scope, families):
        if row.family in stopped:
            continue
        matched, result = _try_row(row, ctx)
        if result is not None:
            return result
        if matched and row.on_match == "stop":
            return None
        if matched and row.on_match == "stop_family":
            stopped.add(row.family)
    return None


def text_match(row_ids: Iterable[str], text: str) -> re.Match[str] | None:
    """The first pattern of the named rows (in the order given) that fully matches `text`: the
    phrase shape alone, no state (M27.6 `gear_phrase`)."""
    table = intent_phrases()
    for row_id in row_ids:
        for regex in _compiled(table, row_id):
            m = regex.fullmatch(text)
            if m is not None:
                return m
    return None
