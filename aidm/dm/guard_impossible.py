"""The guard on impossible actions (M30.1, docs/next/GOAL_IMPOSSIBLE.md): never told as working.

After an `ActionImpossible` this turn, a sentence that tells the attempt working is flagged:
- the attempt's own verb, in any simple form ("I jump onto the house" -> jump, jumps, jumped,
  jumping), said plainly, or
- a success phrase of the lexicon (`impossible_claims`: "manages to", "lands on", "with ease"),
unless the word is negated ("does not jump") or the sentence hedges it (`impossible_hedges`:
"tries", "but", "falls short", "cannot"). The verb is the first word of the attempt text that
is not a lexicon skip word (`impossible_skips`: "I", "try to") and not a creature's name word.
Vocabulary is data (data/bg3/guard_lexicon.json).

Public API: `attempt_forms(state, events, lex) -> frozenset[str] | None` (None: nothing was
impossible this turn), `told_possible(sentence, tokens, forms, lex) -> list[Violation]`.
"""

import re
from collections.abc import Sequence

from aidm.data.guard_lexicon import GuardLexicon
from aidm.dm.guard_text import Token, find_phrases, is_negated, plain
from aidm.dm.guard_types import Violation, ViolationKind
from aidm.models import events as ev
from aidm.models.impossible import ActionImpossible
from aidm.models.state import GameState

_WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")
_MIN_VERB = 3
_VOWELS = frozenset("aeiou")
DETAIL = "that action is impossible: tell the attempt failing or never begun, never working"


def _forms(verb: str) -> set[str]:
    bases = {verb}
    if verb.endswith("s") and len(verb) > _MIN_VERB + 1:
        bases.add(verb[:-1])
    out: set[str] = set()
    for base in bases:
        out |= {base, f"{base}s", f"{base}es", f"{base}ed", f"{base}d", f"{base}ing"}
        if base.endswith("e"):
            out.add(f"{base[:-1]}ing")
        if base.endswith("y") and base[-2] not in _VOWELS:
            out |= {f"{base[:-1]}ies", f"{base[:-1]}ied"}
        if base[-1] not in _VOWELS and base[-2] in _VOWELS and base[-3] not in _VOWELS:
            out |= {f"{base}{base[-1]}ed", f"{base}{base[-1]}ing"}
    return out


def _verb(text: str, skip: frozenset[str]) -> str | None:
    for word in _WORD.findall(plain(text).casefold()):
        if word not in skip:
            return word if len(word) >= _MIN_VERB else None
    return None


def attempt_forms(
    state: GameState, events: Sequence[ev.AnyEvent], lex: GuardLexicon
) -> frozenset[str] | None:
    attempts = [e for e in events if isinstance(e, ActionImpossible)]
    if not attempts:
        return None
    names = {w for c in state.creatures.values() for w in _WORD.findall(plain(c.name).casefold())}
    skip = lex.impossible_skips | names
    forms: set[str] = set()
    for attempt in attempts:
        verb = _verb(attempt.text, skip)
        if verb is not None:
            forms |= _forms(verb)
    return frozenset(forms)


def _token_at(tokens: list[Token], start: int) -> int:
    return next((i for i, t in enumerate(tokens) if t.start >= start), len(tokens))


def told_possible(
    sentence: str, tokens: list[Token], forms: frozenset[str] | None, lex: GuardLexicon
) -> list[Violation]:
    if forms is None or find_phrases(sentence, lex.impossible_hedges):
        return []
    for i, token in enumerate(tokens):
        if token.lower in forms and not is_negated(tokens, i, lex.negations):
            return [Violation(ViolationKind.IMPOSSIBLE_DONE, token.text, DETAIL)]
    for match in find_phrases(sentence, lex.impossible_claims):
        if not is_negated(tokens, _token_at(tokens, match.start()), lex.negations):
            return [Violation(ViolationKind.IMPOSSIBLE_DONE, match.group(0), DETAIL)]
    return []
