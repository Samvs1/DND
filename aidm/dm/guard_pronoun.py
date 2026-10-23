"""Pronoun death claims of the prose guard (QA-03, DECISIONS M9.5).

`guard_alive` links a death claim to a NAME. Live narration also says "he is gone" or "she
breathes her last" about a living hero. A subject pronoun ("he", "she") followed by a death claim
is resolved to the creatures named before it: in the same sentence before the pronoun, else in
the most recent earlier sentence that named someone (`PronounContext`, kept across the sentences
of one narration). The claim is flagged only when EVERY candidate is alive, so a sentence about
a creature that just died ("The goblin falls. He breathes his last.") never trips it.

Death claims: `pronoun_death_claims` (predicates such as "dies", "is dead", "breathes his last"
starting within `PRONOUN_REACH` characters after the pronoun, not negated or hedged; the wider
`death_claims` nouns such as "corpse" are NOT used, since "he kneels by the corpse" is clean)
and `death_soft_claims` ("is gone"), which count only right after the pronoun or name and only
when the sentence has a `death_soft_cues` word ("still", "cold", "breath"): "When you look back,
he is gone." stays clean.

Public API: `PRONOUNS`, `PRONOUN_REACH`, `PronounContext`,
`pronoun_declared_dead(sentence, tokens, scene, context)`.
"""

import re
from dataclasses import dataclass, field

from aidm.data.guard_lexicon import GuardLexicon
from aidm.dm.guard_alive import soft_claim_after
from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases, is_negated
from aidm.dm.guard_types import Violation, ViolationKind

PRONOUNS = frozenset({"he", "she"})
PRONOUN_REACH = 16
_WORD = re.compile(r"[A-Za-z]+")


@dataclass
class PronounContext:
    """Who the last sentence that named anyone named: name -> alive (and name -> still standing,
    for `aidm.dm.guard_truth.pronoun_down`, M29.5c)."""

    last: dict[str, bool] = field(default_factory=dict[str, bool])
    standing: dict[str, bool] = field(default_factory=dict[str, bool])
    last_foe: frozenset[str] = frozenset()  # M29.7b: the foe ids "it" means next (guard_blows)


def _mentions(sentence: str, scene: GuardScene) -> list[tuple[int, str, bool]]:
    found: list[tuple[int, str, bool]] = []
    dead_words = {w for name in scene.dead for w in _WORD.findall(name) if len(w) >= 4}
    terms = [(t, n, True) for t, n in scene.living_terms.items()]
    terms += [(n, n, False) for n in scene.dead] + [(w, w, False) for w in dead_words]
    for term, name, alive in terms:
        pattern = rf"(?<![A-Za-z]){re.escape(term)}(?:'s|s)?(?![A-Za-z])"
        found += [(m.start(), name, alive) for m in re.finditer(pattern, sentence, re.IGNORECASE)]
    return sorted(found)


def _hard_claim_after(sentence: str, tokens: list[Token], end: int, lex: GuardLexicon) -> bool:
    hedges = lex.negations | lex.death_hedges
    for m in find_phrases(sentence[end:], lex.pronoun_death_claims):
        if m.start() > PRONOUN_REACH:
            break
        index = next((i for i, t in enumerate(tokens) if t.start == end + m.start()), None)
        if index is not None and not is_negated(tokens, index, hedges, span=2):
            return True
    return False


def pronoun_declared_dead(
    sentence: str, tokens: list[Token], scene: GuardScene, context: PronounContext
) -> list[Violation]:
    mentions = _mentions(sentence, scene)
    found: list[Violation] = []
    lex = scene.lexicon
    for token in tokens:
        if token.lower not in PRONOUNS or found:
            continue
        before = {name: alive for start, name, alive in mentions if start < token.start}
        candidates = before or context.last
        if not candidates or not all(candidates.values()):
            continue
        if _hard_claim_after(sentence, tokens, token.end, lex) or soft_claim_after(
            sentence, token.end, lex
        ):
            names = ", ".join(sorted(candidates))
            detail = f"'{token.text}' means {names}, who is alive; no engine event killed them"
            found.append(Violation(ViolationKind.LIVING_DECLARED_DEAD, token.text, detail))
    if mentions:
        context.last = {name: alive for _, name, alive in mentions}
    return found
