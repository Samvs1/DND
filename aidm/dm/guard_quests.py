"""Hand-over and quest-outcome checks of the prose guard, both ways (M29.9c, round 3 T10 T11 T21).

Round 3 told a gift the engine made as refused ("Anwen ... pushes it back across the table"
after `KeepsakeGiven`), an accepted quest as finished, and an ally who "joined the party" while
the party stayed four. Each check reads ONE sentence against the frozen `GuardScene` and its
`TurnTruth` (`aidm.dm.guard_turn`); vocabulary is data (data/bg3/guard_lexicon.json):
- `refused_handover`: a `refusal_claims` phrase ("pushes it back", "won't take") in a sentence
  naming an NPC who received something in these events (`TurnTruth.given`);
- `unmade_outcome`: a quest told done (`quest_done_claims`) or failed (`quest_failed_claims`)
  when no quest reached that state in these events; promises ("once the task is done") are not
  claims;
- `denied_outcome`: a quest told undone (`quest_undone_claims`) when one was completed in these
  events;
- `joined_party`: an NPC told joining the party (`join_claims`). The party is its heroes only: no
  engine event adds an NPC to it, so this check also runs for prose about the past (epilogue).
The hand-over the facts lack is `aidm.dm.guard_goods.unmade_handover`.

Public API: `refused_handover`, `unmade_outcome`, `denied_outcome`, `joined_party`.
"""

import re

from aidm.dm.guard_scene import GuardScene, words_of
from aidm.dm.guard_text import Token, find_phrases, is_negated
from aidm.dm.guard_types import Violation, ViolationKind

_MIN_WORD = 4


def _index_at(tokens: list[Token], start: int) -> int | None:
    return next((i for i, t in enumerate(tokens) if t.start == start), None)


def _claim(
    sentence: str, tokens: list[Token], phrases: frozenset[str], scene: GuardScene
) -> re.Match[str] | None:
    for m in find_phrases(sentence, phrases):
        index = _index_at(tokens, m.start())
        if index is not None and not is_negated(tokens, index, scene.lexicon.negations, span=2):
            return m
    return None


def _receivers(scene: GuardScene) -> frozenset[str]:
    lex = scene.lexicon
    skip = lex.titles | lex.sentence_starters
    return frozenset(
        w
        for name in scene.turn.given
        for w in words_of(name)
        if len(w) >= _MIN_WORD and w not in skip
    )


def refused_handover(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth = scene.turn
    if not truth.checked or not truth.given:
        return []
    claim = _claim(sentence, tokens, scene.lexicon.refusal_claims, scene)
    if claim is None or not words_of(sentence) & _receivers(scene):
        return []
    names = ", ".join(sorted(truth.given))
    detail = f"{names} took what was handed over: tell it accepted, not refused or given back"
    return [Violation(ViolationKind.REFUSED_HANDOVER, claim.group(0), detail)]


def unmade_outcome(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth, lex = scene.turn, scene.lexicon
    if not truth.checked or find_phrases(sentence, lex.promise_words):
        return []
    for state, phrases in (
        ("completed", lex.quest_done_claims),
        ("failed", lex.quest_failed_claims),
    ):
        claim = _claim(sentence, tokens, phrases, scene) if state not in truth.outcomes else None
        if claim is not None:
            detail = f"no quest was {state} in these events: tell no quest {state}"
            return [Violation(ViolationKind.UNMADE_OUTCOME, claim.group(0), detail)]
    return []


def denied_outcome(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth = scene.turn
    if not truth.checked or "completed" not in truth.outcomes:
        return []
    claim = _claim(sentence, tokens, scene.lexicon.quest_undone_claims, scene)
    if claim is None:
        return []
    detail = "a quest was completed in these events: do not tell it unfinished"
    return [Violation(ViolationKind.DENIED_OUTCOME, claim.group(0), detail)]


def joined_party(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    claims = find_phrases(sentence, scene.lexicon.join_claims)
    if not claims or not scene.npc_terms:
        return []
    heroes = {w for name in scene.party for w in words_of(name)}
    for m in claims:
        index = _index_at(tokens, m.start())
        if index is None or is_negated(tokens, index, scene.lexicon.negations, span=3):
            continue
        before = [t for t in tokens[:index] if t.text in scene.npc_terms or t.lower in heroes]
        if before and before[-1].lower not in heroes:
            name = scene.npc_terms[before[-1].text]
            detail = (
                f"{name} never joined the party (the party is its heroes): tell them siding with it"
            )
            return [Violation(ViolationKind.JOINED_PARTY, m.group(0), detail)]
    return []
