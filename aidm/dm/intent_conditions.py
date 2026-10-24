"""The named conditions of the typed-intent phrase table (M30.0b): every context rule a row or a
scope depends on, evaluated here and only here (`aidm.dm.intent_match` calls them by name).

- `out_of_fight`: no fight is on (the `explore` scope: nothing there runs in a fight);
- `in_fight`: a fight is on and the actor is one of its combatants;
- `offer_has_parley`: the campaign's encounter offer waits and lists parley (M29.7a R4);
- `no_friend_named`: the sentence names no other hero and not the party ("I ask Elowen ...",
  "I tell the others ...") (M29.7a R4);
- `foe_or_no_bystander` (M29.9a T16): the sentence names one of the offer's foes (a word of a
  monster id or of the master's name), or names no other NPC standing here (name words minus
  filler like "the", "old"); naming a present non-foe NPC is a normal talk turn;
- `no_offer_waits`: no encounter offer waits (travel is the offer's buttons then).

Public API: `Condition`, `CONDITIONS`.
"""

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from aidm.data.intent_phrases import intent_phrases
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.encounter import EncounterStatus
from aidm.models.state import CreatureKind, GameState

if TYPE_CHECKING:
    from aidm.dm.intent_match import Found

type Condition = Callable[["Found"], bool]

_FILLER = frozenset({"the", "of", "and", "old", "young", "a", "an", "in", "at", "to"})


def _fight_on(state: GameState) -> bool:
    enc = state.encounter
    return enc is not None and enc.status is EncounterStatus.ACTIVE


def _offer(state: GameState) -> EncounterOffer | None:
    return state.campaign.offer if state.campaign is not None else None


def out_of_fight(found: "Found") -> bool:
    return not _fight_on(found.state)


def in_fight(found: "Found") -> bool:
    enc = found.state.encounter
    return _fight_on(found.state) and enc is not None and found.actor_id in enc.combatants


def offer_has_parley(found: "Found") -> bool:
    offer = _offer(found.state)
    if offer is None or OfferChoice.PARLEY not in offer.options:
        return False
    return found.actor_id in found.state.creatures


def no_friend_named(found: "Found") -> bool:
    words = found.words
    if words & intent_phrases().lexicon["own_side"]:
        return False
    return not any(
        c.kind is CreatureKind.PC and c.id != found.actor_id and c.name.lower().split()[0] in words
        for c in found.state.creatures.values()
    )


def _name_words(name: str) -> set[str]:
    return set(re.findall(r"[a-z]+", name.lower())) - _FILLER


def foe_or_no_bystander(found: "Found") -> bool:
    state, words = found.state, found.words
    offer = _offer(state)
    if offer is None:
        return True
    foe_words = {w for m in offer.monster_ids for w in m.split("-")}
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if boss is not None:
        foe_words |= _name_words(boss.name)
    if words & foe_words:
        return True
    here = state.world.current_node
    return not any(
        words & (_name_words(n.name) - foe_words)
        for n in state.world.npcs.values()
        if n.node_id == here and not n.dead and n.id != offer.boss_npc_id
    )


def no_offer_waits(found: "Found") -> bool:
    return _offer(found.state) is None


CONDITIONS: dict[str, Condition] = {
    "out_of_fight": out_of_fight,
    "in_fight": in_fight,
    "offer_has_parley": offer_has_parley,
    "no_friend_named": no_friend_named,
    "foe_or_no_bystander": foe_or_no_bystander,
    "no_offer_waits": no_offer_waits,
}
