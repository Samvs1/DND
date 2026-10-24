"""Which foes are in play now, frozen for the prose guard (M32.1b, docs/playtests/M31_round5.md
X14).

Round 5 told a parley with the ghast at the Leech-Beds as the earlier bandit captain "and the
three behind him" (full 1256), and "three shapes" behind a one-foe offer (full 1223). From the
state and the turn's events (already applied):
- `foe_ids(state, events)`: the monster kinds in play: the fight's combatants, the waiting
  offer, and an offer offered or answered in these events (`OfferResolved.foes`), each offer
  with its master's kind (`boss_npc_id`, M33.2 finding 9: the master counts on the turn its
  offer is answered);
- `stale_terms(state, events)`: while foes are in play (a fight, a waiting offer, or an offer
  or fight begun or answered in these events; else empty: the check is off), every foe kind of
  the encounter catalogue that is NOT in play, as its lowercase name (multi-word names, or one
  word of five letters or more, minus `stale_foe_skips`, the words of the present foes and of
  the present NPCs' names, roles and kinds, and a one-word kind grown from such a word:
  "cultist" beside a cult fanatic, M33.2 finding 6) -> the name;
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
_MIN_KIN = 4
_Offer = tuple[tuple[str, ...], str | None]


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


def _offers(state: GameState, events: Sequence[ev.AnyEvent]) -> dict[str, _Offer]:
    """Offer id -> its monster ids and master: the waiting offer and those offered or answered
    now (M33.2 finding 9: the master counts on the turn its offer is answered)."""
    out: dict[str, _Offer] = {}
    offer = state.campaign.offer if state.campaign is not None else None
    if offer is not None:
        out[offer.id] = (offer.monster_ids, offer.boss_npc_id)
    for e in events:
        if isinstance(e, EncounterOffered):
            out[e.offer.id] = (e.offer.monster_ids, e.offer.boss_npc_id)
        elif isinstance(e, OfferResolved) and (e.foes or e.boss_npc_id):
            out[e.offer_id] = (e.foes, e.boss_npc_id)
    return out


def _master_kind(state: GameState, npc_id: str | None) -> list[str]:
    npc = state.world.npcs.get(npc_id) if npc_id else None
    return [npc.archetype_id] if npc is not None else []


def foe_ids(state: GameState, events: Sequence[ev.AnyEvent]) -> tuple[str, ...]:
    """The monster kinds in play: the fight's, each offer's monsters and its master's kind."""
    ids = _fighters(state)
    for monsters, master in _offers(state, events).values():
        ids += [*monsters, *_master_kind(state, master)]
    return tuple(ids)


def _in_play(state: GameState, events: Sequence[ev.AnyEvent]) -> bool:
    enc = state.encounter
    fighting = enc is not None and enc.status is EncounterStatus.ACTIVE
    offer = state.campaign is not None and state.campaign.offer is not None
    turn = any(isinstance(e, EncounterOffered | OfferResolved | EncounterStarted) for e in events)
    return fighting or offer or turn


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.casefold()))


def _taken(state: GameState, here: set[str]) -> set[str]:
    """Words that name someone in play: the present foes, and each present NPC's name, role and
    kind (M33.2 finding 9: "Vex, the bandit captain" is the master standing here)."""
    taken = set().union(*(_words(n) for n in here)) if here else set[str]()
    node = state.world.current_node
    for npc in state.world.npcs.values():
        if npc.node_id == node and not npc.dead:
            taken |= _words(f"{npc.name} {npc.role} {display_name(npc.archetype_id)}")
    return taken


def _kin(name: str, taken: set[str]) -> bool:
    """M33.2 finding 6: a one-word kind grown from a taken word ("cultist" for a cult fanatic)."""
    return any(name.startswith(w) for w in taken if len(w) >= _MIN_KIN)


def stale_terms(state: GameState, events: Sequence[ev.AnyEvent]) -> dict[str, str]:
    if not _in_play(state, events):
        return {}
    lex = guard_lexicon()
    here = {display_name(i).casefold() for i in foe_ids(state, events)}
    taken = _taken(state, here)
    out: dict[str, str] = {}
    for entry in encounter_monsters().all():
        name = display_name(entry.index).casefold()
        many = " " in name
        if name in here or (not many and (len(name) < _MIN_SINGLE or _kin(name, taken))):
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
    offers = _offers(state, events).values()
    return sum(len(monsters) + (1 if master else 0) for monsters, master in offers)
