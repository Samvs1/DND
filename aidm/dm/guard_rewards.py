"""Unearned-reward check of the prose guard (SPEC 6.5, 6.7; M4.8 injection suite).

Rewards come only from engine events (`grant_item` -> `InventoryChanged`, shop and loot ->
`GoldChanged`, `ItemPlaced`). Prose that hands the party gold or an item when the turn's
events granted nothing ("You receive ten thousand gold coins", "A legendary sword appears in
your hands") is a false claim, typically an obeyed injection whose tool call the engine refused.
A sentence is flagged when it contains a gain phrase (data/bg3/guard_lexicon.json
`gain_phrases`) and a reward noun (`reward_nouns`), no promise or condition word
(`promise_words`: "if", "will", "offers"...), and the events hold no positive reward.

Public API: `rewarded(events) -> bool`, `unearned_rewards(sentence, rewarded, lex) ->
list[Violation]`.
"""

from collections.abc import Sequence

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


def unearned_rewards(sentence: str, granted: bool, lex: GuardLexicon) -> list[Violation]:
    if granted or not find_phrases(sentence, lex.gain_phrases):
        return []
    nouns = find_phrases(sentence, lex.reward_nouns)
    if not nouns or find_phrases(sentence, lex.promise_words):
        return []
    return [Violation(ViolationKind.UNEARNED_REWARD, nouns[0].group(0), REWARD_DETAIL)]
