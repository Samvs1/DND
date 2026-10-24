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
- `foe_named` (M31.1a V4): the sentence names a foe of the offer or its master;
- `no_offer_waits`: no encounter offer waits (travel is the offer's buttons then);
- `offer_waits_here` (M32.1a X3, X5): the encounter offer waits at the party's place;
- `hidden_here` (M31.1a V9): something is hidden in the current place (M31.1b: or the place
  teaches an open learn tag);
- `quest_ask_here` (M31.1a V8): a quest offer waits from a living person standing here;
- `no_spell_named` (M32.1a X2): the line names no spell (`dm.spell_names.names_spell`: "hits the
  zombie with a Guiding Bolt" is a cast, never a weapon blow).

Public API: `Condition`, `CONDITIONS`, `foe_words(state)`, `name_words(name)` (the words that name
a person: letters, filler such as "the" and "old" left out).
"""

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from aidm.data.intent_phrases import intent_phrases
from aidm.dm.fight_names import tokens
from aidm.dm.spell_names import names_spell
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.encounter import EncounterStatus
from aidm.models.state import CreatureKind, GameState
from aidm.rules.lore import place_lore_events
from aidm.rules.scene import hidden_dc

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


def name_words(name: str) -> set[str]:
    return set(re.findall(r"[a-z]+", name.lower())) - _FILLER


def foe_words(state: GameState) -> set[str]:
    """The words that name the waiting offer's foes: a word of a monster id or of the master's
    name (empty with no offer)."""
    offer = _offer(state)
    if offer is None:
        return set()
    words = {w for m in offer.monster_ids for w in m.split("-") if not w.isdigit()}
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    return words | name_words(boss.name) if boss is not None else words


def foe_or_no_bystander(found: "Found") -> bool:
    state, words = found.state, found.words
    offer = _offer(state)
    if offer is None:
        return True
    foes = foe_words(state)
    if words & foes:
        return True
    here = state.world.current_node
    return not any(
        words & (name_words(n.name) - foes)
        for n in state.world.npcs.values()
        if n.node_id == here and not n.dead and n.id != offer.boss_npc_id
    )


def foe_named(found: "Found") -> bool:
    """M31.1a V4: the sentence names a foe of the waiting offer or its master."""
    return bool(found.words & foe_words(found.state))


def hidden_here(found: "Found") -> bool:
    """M31.1a V9: something is hidden in the current place (a search can find it); M31.1b V13c:
    or the place teaches an open learn tag (a search there records it)."""
    found_lore = place_lore_events(found.state, found.actor_id)
    return hidden_dc(found.state) is not None or bool(found_lore)


def offer_waits_here(found: "Found") -> bool:
    offer = _offer(found.state)
    return offer is not None and offer.node_id == found.state.world.current_node


def no_offer_waits(found: "Found") -> bool:
    return _offer(found.state) is None


def quest_ask_here(found: "Found") -> bool:
    """M31.1a V8: a quest offer waits from a living person who stands here."""
    world = found.state.world
    ask = world.quest_ask
    npc = world.npcs.get(ask.npc_id) if ask is not None else None
    return npc is not None and not npc.dead and npc.node_id == world.current_node


def no_spell_named(found: "Found") -> bool:
    actor = found.state.creatures.get(found.actor_id)
    return actor is None or not names_spell(actor, tokens(found.text))


CONDITIONS: dict[str, Condition] = {
    "out_of_fight": out_of_fight,
    "in_fight": in_fight,
    "offer_has_parley": offer_has_parley,
    "no_friend_named": no_friend_named,
    "foe_or_no_bystander": foe_or_no_bystander,
    "foe_named": foe_named,
    "hidden_here": hidden_here,
    "no_offer_waits": no_offer_waits,
    "offer_waits_here": offer_waits_here,
    "quest_ask_here": quest_ask_here,
    "no_spell_named": no_spell_named,
}
