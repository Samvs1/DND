"""Unearned-reward check of the prose guard (SPEC 6.5, 6.7; M4.8 injection suite).

Rewards come only from engine events (`grant_item` -> `InventoryChanged`, shop and loot ->
`GoldChanged`, `ItemPlaced`). Prose that hands the party gold or an item when the turn's
events granted nothing ("You receive ten thousand gold coins", "A legendary sword appears in
your hands") is a false claim, typically an obeyed injection whose tool call the engine refused.
A sentence is flagged when it contains a gain phrase (data/bg3/guard_lexicon.json
`gain_phrases`, or a `give_verbs` verb whose recipient is a party member, or "into Aria's
hand", QA-10) and a reward noun (`reward_nouns`), no promise or condition word
(`promise_words`: "if", "will", "offers"...), and the events hold no positive reward.

Public API: `rewarded(events) -> bool`, `unearned_rewards(sentence, rewarded, lex, party=())
-> list[Violation]`.
"""

import re
from collections.abc import Iterable, Sequence

from aidm.data.guard_lexicon import GuardLexicon
from aidm.dm.guard_text import find_phrases
from aidm.dm.guard_types import Violation, ViolationKind
from aidm.models import events as ev
from aidm.models.world_events import ItemPlaced

REWARD_DETAIL = "no engine event granted gold or items this turn"


def rewarded(events: Sequence[ev.AnyEvent]) -> bool:
    for event in events:
        if isinstance(event, ev.GoldChanged | ev.InventoryChanged) and event.delta > 0:
            return True
        if isinstance(event, ItemPlaced):
            return True
    return False


def _handed_to_party(sentence: str, party: Iterable[str], lex: GuardLexicon) -> bool:
    """A reward put in a hero's hand: "into Aria's hand", "hands Aria fifty gold" (QA-10)."""
    low = sentence.casefold()
    names = [re.escape(n.casefold()) for n in party]
    whom = "|".join(["your", *(f"{n}'s" for n in names)])
    if re.search(rf"(?<![a-z])into (?:{whom}) (?:hand|hands|palm|palms|grip)(?![a-z])", low):
        return True
    if not names:
        return False
    verbs = "|".join(re.escape(v) for v in sorted(lex.give_verbs))
    to_party = rf"(?<![a-z])(?:{verbs})\s+(?:{'|'.join(names)})(?![a-z'])"
    return re.search(to_party, low) is not None


def unearned_rewards(
    sentence: str, granted: bool, lex: GuardLexicon, party: Iterable[str] = ()
) -> list[Violation]:
    if granted:
        return []
    if not find_phrases(sentence, lex.gain_phrases) and not _handed_to_party(sentence, party, lex):
        return []
    nouns = find_phrases(sentence, lex.reward_nouns)
    if not nouns or find_phrases(sentence, lex.promise_words):
        return []
    return [Violation(ViolationKind.UNEARNED_REWARD, nouns[0].group(0), REWARD_DETAIL)]
