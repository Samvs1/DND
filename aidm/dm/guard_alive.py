"""Living-declared-dead check of the prose guard (SPEC 6.5, 6.7; M4.8 injection suite).

The engine owns life and death: a creature dies only through damage events (`CreatureDied`,
already applied to the state before narration). Prose that declares a LIVING creature, NPC or
party member dead ("the dragon is dead now", "Mira lies dead") is a false claim, typically an
obeyed player injection. A living name (full name, or a distinctive word of it of >= 4 letters
that no dead creature shares, e.g. "dragon" for "Young Red Dragon") followed within
`CLAIM_REACH` characters by a death claim (data/bg3/guard_lexicon.json `death_claims`) that is
neither negated ("not dead") nor hedged ("nearly dead", `death_hedges`) is flagged.

Public API: `CLAIM_REACH`, `living_terms(state, dead, lex) -> dict[str, str]` (term -> name),
`living_declared_dead(sentence, tokens, terms, lex) -> list[Violation]`.
"""

import re

from aidm.data.guard_lexicon import GuardLexicon
from aidm.dm.guard_text import Token, find_phrases, is_negated
from aidm.dm.guard_types import Violation, ViolationKind
from aidm.models.state import GameState

CLAIM_REACH = 40
MIN_TERM_LEN = 4
_WORD = re.compile(r"[A-Za-z]+")


def _living_names(state: GameState) -> set[str]:
    names = {c.name for c in state.creatures.values() if not c.dead}
    dead_names = {c.name for c in state.creatures.values() if c.dead}
    names |= {n.name for n in state.world.npcs.values() if n.name not in dead_names}
    return names


def living_terms(state: GameState, dead: frozenset[str], lex: GuardLexicon) -> dict[str, str]:
    dead_words = {w.casefold() for name in dead for w in _WORD.findall(name)}
    terms: dict[str, str] = {}
    for name in sorted(_living_names(state)):
        terms[name] = name
        for word in _WORD.findall(name):
            low = word.casefold()
            skip = low in dead_words or low in lex.titles or low in lex.sentence_starters
            if len(word) >= MIN_TERM_LEN and not skip:
                terms.setdefault(word, name)
    return terms


def _index_at(tokens: list[Token], start: int) -> int | None:
    return next((i for i, t in enumerate(tokens) if t.start == start), None)


def _claimed(sentence: str, tokens: list[Token], end: int, lex: GuardLexicon) -> bool:
    for m in find_phrases(sentence[end : end + CLAIM_REACH], lex.death_claims):
        index = _index_at(tokens, end + m.start())
        if index is None:
            continue
        hedges = lex.negations | lex.death_hedges
        if not is_negated(tokens, index, hedges, span=2):
            return True
    return False


def living_declared_dead(
    sentence: str, tokens: list[Token], terms: dict[str, str], lex: GuardLexicon
) -> list[Violation]:
    if not terms or not find_phrases(sentence, lex.death_claims):
        return []
    for term in sorted(terms, key=lambda t: (-len(t), t)):
        pattern = rf"(?<![A-Za-z]){re.escape(term)}(?:'s|s)?(?![A-Za-z])"
        for m in re.finditer(pattern, sentence, re.IGNORECASE):
            if _claimed(sentence, tokens, m.end(), lex):
                name = terms[term]
                detail = f"{name} is alive; no engine event killed them"
                return [Violation(ViolationKind.LIVING_DECLARED_DEAD, m.group(0), detail)]
    return []
