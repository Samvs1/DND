"""Found things, hand-over recipients and quest answers (M31.1c, docs/playtests/M31_round4.md V17
V18). Round 4 told searched things tucked away while they still lay on the ground (full 463, 605,
624), a gift to Sister Thena pressed into the peddler's palm (full 544) and a quest still waiting
for the players' answer as accepted (full 745). Each check reads ONE sentence against the frozen
`GuardScene` and its `TurnTruth` (`aidm.dm.guard_turn`); vocabulary is data
(data/bg3/guard_lexicon.json):
- `found_taken`: while something these events found still lies where it was found
  (`TurnTruth.found`), a `keep_claims` phrase ("tucks them away", "pockets", "comes up with");
- `wrong_recipient`: a `recipient_verbs` verb ("presses", "hands") whose "to/into the X" names an
  NPC who received nothing in these events, while someone else did (`TurnTruth.given`);
- `quest_accepted`: while a quest offer waits for the players' answer (`TurnTruth.asked`), an
  `accept_claims` phrase ("you accept", "the bargain is struck"), unless negated or hedged
  (`accept_hedges`: "whether you take up the task").

Public API: `found_taken`, `wrong_recipient`, `quest_accepted`.
"""

import re

from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import Token, find_phrases, is_negated
from aidm.dm.guard_types import Violation, ViolationKind

_TO_REACH = 6  # words between the verb and "to/into"


def _index_at(tokens: list[Token], start: int) -> int | None:
    return next((i for i, t in enumerate(tokens) if t.start >= start), None)


def _unnegated(
    sentence: str, tokens: list[Token], phrases: frozenset[str], scene: GuardScene
) -> re.Match[str] | None:
    for m in find_phrases(sentence, phrases):
        index = _index_at(tokens, m.start())
        if index is not None and not is_negated(tokens, index, scene.lexicon.negations, span=2):
            return m
    return None


def found_taken(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth, lex = scene.turn, scene.lexicon
    if not truth.checked or not truth.found or find_phrases(sentence, lex.promise_words):
        return []
    claim = _unnegated(sentence, tokens, lex.keep_claims, scene)
    if claim is None:
        return []
    things = ", ".join(sorted(truth.found))
    detail = f"{things} was found, not taken: it still lies where it was found, nobody holds it"
    return [Violation(ViolationKind.FOUND_TAKEN, claim.group(0), detail)]


def _recipient(sentence: str, end: int, scene: GuardScene) -> tuple[str, str] | None:
    terms = "|".join(re.escape(t) for t in sorted(scene.npc_terms, key=len, reverse=True))
    if not terms:
        return None
    pattern = (
        rf"^(?:\s+[\w'-]+){{0,{_TO_REACH}}}?\s+(?:to|into)\s+(?:the\s+|a\s+|an\s+)?"
        rf"(?:[a-z-]+\s+)?({terms})(?![A-Za-z])"
    )
    m = re.match(pattern, sentence[end:], re.IGNORECASE)
    if m is None:
        return None
    term = next(t for t in scene.npc_terms if t.casefold() == m.group(1).casefold())
    return m.group(1), scene.npc_terms[term]


def wrong_recipient(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth = scene.turn
    if not truth.checked or not truth.given:
        return []
    for verb in find_phrases(sentence, scene.lexicon.recipient_verbs):
        found = _recipient(sentence, verb.end(), scene)
        if found is None or found[1] in truth.given:
            continue
        given = ", ".join(sorted(truth.given))
        detail = f"the thing went to {given}, not to {found[1]}: tell {given} receiving it"
        return [Violation(ViolationKind.WRONG_RECIPIENT, found[0], detail)]
    return []


def quest_accepted(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    truth, lex = scene.turn, scene.lexicon
    if not truth.checked or not truth.asked or find_phrases(sentence, lex.accept_hedges):
        return []
    claim = _unnegated(sentence, tokens, lex.accept_claims, scene)
    if claim is None:
        return []
    detail = (
        f"{truth.asked}'s offer is waiting for the players' answer: nobody accepted or agreed yet"
    )
    return [Violation(ViolationKind.QUEST_ACCEPTED, claim.group(0), detail)]
