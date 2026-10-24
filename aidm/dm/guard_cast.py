"""The guard on spells told cast with no cast (M30.2b: no free spells by typing).

A spell happens only through the engine (`rules.spells`: the slot or resource is spent and a
`SpellCast` is recorded). A sentence that tells a spell of the engine's registry being cast
("Brienne casts Misty Step", "you cast a quick bless") when these events hold no `SpellCast` of
that spell, and no monster action of that name, is flagged:
- a cast verb of the lexicon (`cast_verbs`: cast, casts, casting, invokes ...) followed, at most
  three words on, by the spell's name (its id words: "misty step", "hunters mark"); no word
  between may be a `cast_gap_stops` word ("shadows cast on the web" casts no Web);
- unless the verb is negated ("does not cast") or the sentence hedges it (`cast_hedges`:
  "tries to", "prepares to", "would", "cannot", "no slot").
Vocabulary is data (data/bg3/guard_lexicon.json). Prose about the past (`TurnTruth()` unchecked:
the epilogue) and an NPC's own speech are not judged.

Public API: `cast_spells(events) -> frozenset[str]` (the spell ids and monster action names cast
in these events, normalised), `untold_cast(sentence, tokens, cast, lex) -> list[Violation]`,
`known_spells(state, events) -> list[str]` (the spell names prose may use: the heroes' ready
spells and the spells cast in these events; `aidm.dm.guard_scene` adds their words to the known
words, so "Misty Step" is never an unknown person).
"""

import functools
import re
from collections.abc import Sequence

from aidm.data.combat_data import combat_registries
from aidm.data.guard_lexicon import GuardLexicon
from aidm.dm.entities import display_name
from aidm.dm.guard_text import Token, find_phrases, is_negated, plain, tokenize
from aidm.dm.guard_types import Violation, ViolationKind
from aidm.models import events as ev
from aidm.models.combat_events import MonsterActionUsed, SpellCast
from aidm.models.state import GameState

DETAIL = (
    "no spell was cast by the engine for that: never tell a spell cast or working that the events"
    " do not list"
)
_REACH = 3


def _norm(text: str) -> str:
    return re.sub(r"[-/]", " ", plain(text).casefold().replace("'", ""))


@functools.cache
def _spell_names() -> dict[str, str]:
    """Normalised spell name ("misty step") -> spell id, for every spell of the engine."""
    return {s.index.replace("-", " "): s.index for s in combat_registries().spells.all()}


def _alternatives(words: frozenset[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


@functools.cache
def _pattern(verbs: frozenset[str], stops: frozenset[str]) -> re.Pattern[str]:
    verb = _alternatives(verbs)
    names = sorted(_spell_names(), key=len, reverse=True)
    name = "|".join(r"\s+".join(re.escape(w) for w in n.split()) for n in names)
    stop = rf"(?!(?:{_alternatives(stops)})\b)" if stops else ""
    gap = rf"(?:\s+{stop}[a-z]+){{0,{_REACH}}}?"
    return re.compile(rf"\b(?P<verb>{verb})\b{gap}\s+(?P<spell>{name})\b")


def cast_spells(events: Sequence[ev.AnyEvent]) -> frozenset[str]:
    out = {e.spell_id for e in events if isinstance(e, SpellCast)}
    for e in events:
        if isinstance(e, MonsterActionUsed):
            low = _norm(e.name)
            out |= {sid for name, sid in _spell_names().items() if name in low}
    return frozenset(out)


def known_spells(state: GameState, events: Sequence[ev.AnyEvent]) -> list[str]:
    """Display names of the spells the heroes have ready and of those cast in these events: real
    engine entries, so the names are never unknown names in prose (the sheet lists them, M30.2)."""
    ready = [
        i
        for c in state.creatures.values()
        if (pc := c.pc) is not None
        for i in (*pc.cantrips, *pc.race_cantrips, *pc.spells_known, *pc.prepared)
    ]
    cast = [e.spell_id for e in events if isinstance(e, SpellCast)]
    return [display_name(i) for i in dict.fromkeys([*ready, *cast])]


def _negated(sentence: str, start: int, lex: GuardLexicon) -> bool:
    tokens = tokenize(sentence)
    index = next((i for i, t in enumerate(tokens) if t.start >= start), len(tokens))
    return is_negated(tokens, index, lex.negations)


def untold_cast(
    sentence: str, tokens: list[Token], cast: frozenset[str] | None, lex: GuardLexicon
) -> list[Violation]:
    del tokens  # the cast pattern reads the normalised sentence
    if cast is None or not lex.cast_verbs or find_phrases(sentence, lex.cast_hedges):
        return []
    low = _norm(sentence)
    for match in _pattern(lex.cast_verbs, lex.cast_gap_stops).finditer(low):
        spell = _spell_names()[" ".join(match.group("spell").split())]
        if spell not in cast and not _negated(low, match.start(), lex):
            return [Violation(ViolationKind.UNCAST_SPELL, match.group(0), DETAIL)]
    return []
