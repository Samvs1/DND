"""Which foes are in play now, frozen for the prose guard (M32.1b, docs/playtests/M31_round5.md
X14).

Round 5 told a parley with the ghast at the Leech-Beds as the earlier bandit captain "and the
three behind him" (full 1256), and "three shapes" behind a one-foe offer (full 1223). From the
state and the turn's events (already applied):
- `foe_ids(state, events)`: the monster kinds in play: the fight's combatants, the waiting
  offer, and an offer offered or answered in these events (`OfferResolved.foes`);
- `stale_terms(state, events)`: while foes are in play (a fight, a waiting offer, or an offer
  or fight begun or answered in these events; else empty: the check is off), every foe kind of
  the encounter catalogue that is NOT in play, as its lowercase name (multi-word names, or one
  word of five letters or more, minus `stale_foe_skips` and the words of the present foes, NPC
  names and roles) -> the name;
- `foes_here(state, events)`: how many foes an offer holds (the waiting offer, or one offered or
  answered in these events: monsters and master); 0 during a fight (debris "shapes" are told
  there; `guard_counts.foe_counts` counts the fight's foe kinds).

Public API: `foe_ids`, `stale_terms`, `foes_here`.
"""

import re
from collections.abc import Sequence

from aidm.data.encounter_monsters import encounter_monsters
from aidm.data.guard_lexicon import guard_lexicon
from aidm.dm.entities import display_name
from aidm.models import events as ev
from aidm.models.campaign_events import EncounterOffered, OfferResolved
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterStarted
from aidm.models.state import GameState

_MIN_SINGLE = 5


def _fighters(state: GameState) -> list[str]:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return []
    out: list[str] = []
    for c in enc.combatants.values():
        creature = state.creatures.get(c.creature_id)
        if creature is not None and creature.pc is None:
            out.append(creature.monster_index or creature.name.lower().replace(" ", "-"))
    return out


def _offers(state: GameState, events: Sequence[ev.AnyEvent]) -> dict[str, tuple[str, ...]]:
    """Offer id -> its monster ids: the waiting offer and those offered or answered now."""
    out: dict[str, tuple[str, ...]] = {}
    offer = state.campaign.offer if state.campaign is not None else None
    if offer is not None:
        out[offer.id] = offer.monster_ids
    for e in events:
        if isinstance(e, EncounterOffered):
            out[e.offer.id] = e.offer.monster_ids
        elif isinstance(e, OfferResolved) and e.foes:
            out[e.offer_id] = e.foes
    return out


def foe_ids(state: GameState, events: Sequence[ev.AnyEvent]) -> tuple[str, ...]:
    ids = _fighters(state)
    for monsters in _offers(state, events).values():
        ids += monsters
    return tuple(ids)


def _in_play(state: GameState, events: Sequence[ev.AnyEvent]) -> bool:
    enc = state.encounter
    fighting = enc is not None and enc.status is EncounterStatus.ACTIVE
    offer = state.campaign is not None and state.campaign.offer is not None
    turn = any(isinstance(e, EncounterOffered | OfferResolved | EncounterStarted) for e in events)
    return fighting or offer or turn


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.casefold()))


def stale_terms(state: GameState, events: Sequence[ev.AnyEvent]) -> dict[str, str]:
    if not _in_play(state, events):
        return {}
    lex = guard_lexicon()
    here = {display_name(i).casefold() for i in foe_ids(state, events)}
    taken = set().union(*(_words(n) for n in here)) if here else set[str]()
    node = state.world.current_node
    for npc in state.world.npcs.values():
        if npc.node_id == node and not npc.dead:
            taken |= _words(f"{npc.name} {npc.role}")
    out: dict[str, str] = {}
    for entry in encounter_monsters().all():
        name = display_name(entry.index).casefold()
        many = " " in name
        if name in here or (not many and len(name) < _MIN_SINGLE):
            continue
        if name in lex.stale_foe_skips or _words(name) <= taken:
            continue
        out[name] = display_name(entry.index)
    return out


def foes_here(state: GameState, events: Sequence[ev.AnyEvent]) -> int:
    """How many foes an offer holds (its monsters and its master), outside a fight; 0 in a fight
    (the fight's own foe-kind count runs there) or with no offer: the figure check is off."""
    if _fighters(state):
        return 0
    offer = state.campaign.offer if state.campaign is not None else None
    master = 1 if offer is not None and offer.boss_npc_id else 0
    return sum(len(m) for m in _offers(state, events).values()) + master
