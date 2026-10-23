"""Living-declared-dead check of the prose guard (SPEC 6.5, 6.7; M4.8 injection suite).

The engine owns life and death: a creature dies only through damage events (`CreatureDied`,
already applied to the state before narration). Prose that declares a LIVING creature, NPC or
party member dead ("the dragon is dead now", "Mira lies dead") is a false claim, typically an
obeyed player injection. A living name (full name, or a distinctive word of it of >= 4 letters
that no dead creature shares, e.g. "dragon" for "Young Red Dragon") followed within
`CLAIM_REACH` characters by a death claim (data/bg3/guard_lexicon.json `death_claims`) that is
neither negated ("not dead") nor hedged ("nearly dead", `death_hedges`) is flagged.

"Bob is gone" (`death_soft_claims`) counts only right after the name and only when a
stillness cue follows it (`death_soft_cues`, QA-03: "he is gone, still and cold").

A creature that still has hit points (or an NPC outside a fight) declared down, out cold or
beaten (`defeat_claims`, M19.1: the narrator told a whole fight as won while it had only begun)
is flagged by `unhurt_declared_down` with the terms of `standing_terms` (M29.5c G21: anywhere in
the clause after the name, up to `DOWN_REACH` characters).
A hero at 0 HP told waking, standing or coming to (`rise_claims`) with no healing event is
flagged by `downed_rising` with the terms of `downed_terms` (M20.2).

Public API: `CLAIM_REACH`, `living_terms(state, dead, lex) -> dict[str, str]` (term -> name),
`standing_terms(state, terms) -> dict[str, str]`, `downed_terms(state, dead, lex)`,
`soft_claim_after(sentence, end, lex) -> bool`, `downed_rising(sentence, tokens, terms, lex)`,
`living_declared_dead(sentence, tokens, terms, lex) -> list[Violation]`,
`unhurt_declared_down(sentence, tokens, terms, lex) -> list[Violation]`.
"""

import re

from aidm.data.guard_lexicon import GuardLexicon
from aidm.dm.guard_text import Token, find_phrases, is_negated
from aidm.dm.guard_types import Violation, ViolationKind
from aidm.models.state import GameState

CLAIM_REACH = 40
DOWN_REACH = 90  # M29.5c G21: "the zombie drops face-first onto the stones and lies still"
MIN_TERM_LEN = 4
_WORD = re.compile(r"[A-Za-z]+")
_CLAUSE = re.compile(r"\b(?:while|whilst|as|when|but|though|until|before|after)\b|[;:]", re.I)
_DOWN_CLAUSE = re.compile(rf"{_CLAUSE.pattern}|,", re.I)


def _living_names(state: GameState) -> set[str]:
    names = {c.name for c in state.creatures.values() if not c.dead}
    dead_names = {c.name for c in state.creatures.values() if c.dead}
    names |= {n.name for n in state.world.npcs.values() if n.name not in dead_names and not n.dead}
    return names


def living_terms(state: GameState, dead: frozenset[str], lex: GuardLexicon) -> dict[str, str]:
    return _terms(_living_names(state), dead, lex)


def downed_terms(state: GameState, dead: frozenset[str], lex: GuardLexicon) -> dict[str, str]:
    """M20.2: the living at 0 HP (only an engine event raises them)."""
    downed = {c.name for c in state.creatures.values() if not c.dead and c.hp <= 0}
    return _terms(downed, dead, lex)


def _terms(names: set[str], dead: frozenset[str], lex: GuardLexicon) -> dict[str, str]:
    dead_words = {w.casefold() for name in dead for w in _WORD.findall(name)}
    terms: dict[str, str] = {}
    for name in sorted(names):
        terms[name] = name
        for word in _WORD.findall(name):
            low = word.casefold()
            skip = low in dead_words or low in lex.titles or low in lex.sentence_starters
            if len(word) >= MIN_TERM_LEN and not skip:
                terms.setdefault(word, name)
    return terms


def _index_at(tokens: list[Token], start: int) -> int | None:
    return next((i for i, t in enumerate(tokens) if t.start == start), None)


def standing_terms(state: GameState, terms: dict[str, str]) -> dict[str, str]:
    """The living terms minus anyone at 0 hit points (a downed hero may be told unconscious) and
    any term sharing a word with a fallen creature ("the fallen goblin lies still" next to a
    living goblin is about the dead one)."""
    fallen = [c.name for c in state.creatures.values() if c.dead or c.hp <= 0]
    fallen_words = {w.casefold() for name in fallen for w in _WORD.findall(name)}
    return {
        term: name
        for term, name in terms.items()
        if name not in fallen and not {w.casefold() for w in _WORD.findall(term)} & fallen_words
    }


def _claimed(
    sentence: str,
    tokens: list[Token],
    end: int,
    lex: GuardLexicon,
    claims: frozenset[str],
    reach: int = CLAIM_REACH,
) -> bool:
    for m in find_phrases(sentence[end : end + reach], claims):
        index = _index_at(tokens, end + m.start())
        if index is None:
            continue
        hedges = lex.negations | lex.death_hedges
        if not is_negated(tokens, index, hedges, span=2):
            return True
    return False


def soft_claim_after(sentence: str, end: int, lex: GuardLexicon) -> bool:
    """A `death_soft_claims` phrase right after `end`, followed by a stillness cue."""
    rest = sentence[end:].lstrip().casefold()
    claim = next(
        (m for p in lex.death_soft_claims if (m := re.match(rf"{re.escape(p)}(?![a-z])", rest))),
        None,
    )
    return claim is not None and bool(find_phrases(rest[claim.end() :], lex.death_soft_cues))


def living_declared_dead(
    sentence: str, tokens: list[Token], terms: dict[str, str], lex: GuardLexicon
) -> list[Violation]:
    claims = lex.death_claims | lex.death_soft_claims
    if not terms or not find_phrases(sentence, claims):
        return []
    for term in sorted(terms, key=lambda t: (-len(t), t)):
        pattern = rf"(?<![A-Za-z]){re.escape(term)}(?:'s|s)?(?![A-Za-z])"
        for m in re.finditer(pattern, sentence, re.IGNORECASE):
            claimed = _claimed(sentence, tokens, m.end(), lex, lex.death_claims)
            if claimed or soft_claim_after(sentence, m.end(), lex):
                name = terms[term]
                detail = f"{name} is alive; no engine event killed them"
                return [Violation(ViolationKind.LIVING_DECLARED_DEAD, m.group(0), detail)]
    return []


def unhurt_declared_down(
    sentence: str, tokens: list[Token], terms: dict[str, str], lex: GuardLexicon
) -> list[Violation]:
    if not terms or not find_phrases(sentence, lex.defeat_claims):
        return []
    for term in sorted(terms, key=lambda t: (-len(t), t)):
        pattern = rf"(?<![A-Za-z]){re.escape(term)}(?:'s|s)?(?![A-Za-z])"
        for m in re.finditer(pattern, sentence, re.IGNORECASE):
            end = _clause_end(sentence, m.end(), _DOWN_CLAUSE)
            reach = min(end - m.end(), DOWN_REACH)  # M29.5c G21: the clause after the name
            if _claimed(sentence, tokens, m.end(), lex, lex.defeat_claims, reach):
                detail = f"{terms[term]} is still standing; no engine event beat them"
                return [Violation(ViolationKind.UNHURT_DECLARED_DOWN, m.group(0), detail)]
    return []


def _clause_end(sentence: str, start: int, clause: re.Pattern[str] = _CLAUSE) -> int:
    """Where the clause after a name ends ("Slendee lies still while the ranger gets up")."""
    found = clause.search(sentence, start)
    return found.start() if found is not None else len(sentence)


def downed_rising(
    sentence: str, tokens: list[Token], terms: dict[str, str], lex: GuardLexicon
) -> list[Violation]:
    """A hero at 0 HP told waking, standing or coming to with no healing event (M20.2: "her
    breathing steadies" was told while nothing had happened)."""
    if not terms or not find_phrases(sentence, lex.rise_claims):
        return []
    for term in sorted(terms, key=lambda t: (-len(t), t)):
        pattern = rf"(?<![A-Za-z]){re.escape(term)}(?:'s|s)?(?![A-Za-z])"
        for m in re.finditer(pattern, sentence, re.IGNORECASE):
            clause = sentence[: _clause_end(sentence, m.end())]
            if _claimed(clause, tokens, m.end(), lex, lex.rise_claims):
                detail = f"{terms[term]} is down at 0 HP; no engine event raised them"
                return [Violation(ViolationKind.DOWNED_RISING, m.group(0), detail)]
    return []
