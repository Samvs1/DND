"""Handing things to another hero (M29.7a R8, owner rule: a physically possible action happens;
docs/next/GOAL_ITEMS.md "data adds effects, it never forbids actions"). Pure: returns events.

`hand_events(state, giver_id, receiver_id, regs, *, thing=None, qty=1, gold=0)` serves the
`hand_over` client command and the typed "hand the crowbar to Elowen" / "give Elowen 30 gold"
alike. `thing` is an inventory item key (`qty` copies; a worn copy that cannot stay worn comes
off first, `rules.equipment.release_events`) or the id of a keepsake the giver carries; `gold`
moves coins. Events: `InventoryChanged` / `GoldChanged` for both heroes and one `HandedOver`
record (which moves a keepsake itself).
Only the physically impossible is refused, each with a plain reason: a giver who is dead or down,
a receiver who is dead, unknown or the giver, something the giver does not carry (or not that
many), more gold than the giver has, nothing at all, and in a fight a receiver in another zone
(out of reach; RULES_DECISIONS M29.7a: handing over in reach is free, as in BG3).

M36.4 (round 6 Y14: a fallen hero's pack had no path): `loot_events(state, taker_id, from_id,
regs, *, thing=None, qty=1, gold=0)` is the same move the other way: a living hero takes from the
pack of a downed or dead hero, out of a fight (DECISIONS M36.0: physically possible, so allowed).
The same events, the `HandedOver` record marked `taken`. Refused plainly: a taker who is down or
not a hero, a source who is awake (they hand it over themselves) or not a hero, a fight going on,
and the same "not carried" / "only n" / gold answers as handing.

Public API: `HandRefused(detail)`, `hand_events(...)`, `loot_events(...) -> list[AnyEvent]`.
"""

from aidm.data.character_data import CharacterRegistries
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, GoldChanged, InventoryChanged
from aidm.models.item_events import HandedOver
from aidm.models.state import Creature, GameState
from aidm.rules.equipment import release_events
from aidm.rules.item_effects import gear_name
from aidm.rules.item_grants import carried_qty


class HandRefused(ValueError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _heroes(state: GameState, giver_id: str, receiver_id: str) -> tuple[Creature, Creature]:
    giver = state.creatures.get(giver_id)
    taker = state.creatures.get(receiver_id)
    if giver is None or giver.pc is None or giver.dead or giver.hp <= 0:
        raise HandRefused("Your hero cannot hand anything over right now.")
    if taker is None or taker.pc is None:
        raise HandRefused("There is no hero like that in the party.")
    if taker.id == giver.id:
        raise HandRefused(f"{giver.name} already holds it.")
    if taker.dead:
        raise HandRefused(f"{taker.name} is dead and can take nothing.")
    enc = state.encounter
    if enc is not None and enc.status is EncounterStatus.ACTIVE:
        here = enc.combatants.get(giver.id)
        there = enc.combatants.get(taker.id)
        if here is not None and there is not None and here.zone_id != there.zone_id:
            raise HandRefused(f"{taker.name} is out of reach in this fight.")
    return giver, taker


def _thing_events(
    giver: Creature,
    taker: Creature,
    thing: str,
    qty: int,
    regs: CharacterRegistries,
    taken: bool = False,
) -> list[AnyEvent]:
    assert giver.pc is not None
    if any(k.id == thing for k in giver.pc.keepsakes):
        return [HandedOver(creature_id=giver.id, to_id=taker.id, keepsake_id=thing, taken=taken)]
    carried = carried_qty(giver, thing)
    if carried < 1:
        raise HandRefused(f"{giver.name} does not carry that.")
    if carried < qty:
        raise HandRefused(f"{giver.name} carries only {carried} {gear_name(thing).lower()}.")
    have = carried_qty(taker, thing)
    return [
        *release_events(giver, thing, regs, qty),
        InventoryChanged(creature_id=giver.id, item=thing, delta=-qty, qty=carried - qty),
        InventoryChanged(creature_id=taker.id, item=thing, delta=qty, qty=have + qty),
        HandedOver(creature_id=giver.id, to_id=taker.id, item=thing, qty=qty, taken=taken),
    ]


def _gold_events(
    giver: Creature, taker: Creature, gold: int, taken: bool = False
) -> list[AnyEvent]:
    assert giver.pc is not None and taker.pc is not None
    if gold > giver.pc.gold:
        raise HandRefused(f"{giver.name} has only {giver.pc.gold} gold.")
    return [
        GoldChanged(creature_id=giver.id, delta=-gold, gold=giver.pc.gold - gold),
        GoldChanged(creature_id=taker.id, delta=gold, gold=taker.pc.gold + gold),
        HandedOver(creature_id=giver.id, to_id=taker.id, gold=gold, taken=taken),
    ]


def hand_events(
    state: GameState,
    giver_id: str,
    receiver_id: str,
    regs: CharacterRegistries,
    *,
    thing: str | None = None,
    qty: int = 1,
    gold: int = 0,
) -> list[AnyEvent]:
    giver, taker = _heroes(state, giver_id, receiver_id)
    if (thing is None or qty < 1) and gold < 1:
        raise HandRefused("Nothing to hand over.")
    events: list[AnyEvent] = []
    if thing is not None and qty >= 1:
        events += _thing_events(giver, taker, thing, qty, regs)
    if gold >= 1:
        events += _gold_events(giver, taker, gold)
    return events


def _looting(state: GameState, taker_id: str, from_id: str) -> tuple[Creature, Creature]:
    taker = state.creatures.get(taker_id)
    fallen = state.creatures.get(from_id)
    if taker is None or taker.pc is None or taker.dead or taker.hp <= 0:
        raise HandRefused("Your hero cannot take anything right now.")
    if fallen is None or fallen.pc is None or fallen.id == taker.id:
        raise HandRefused("There is no fallen hero like that in the party.")
    if not fallen.dead and fallen.hp > 0:
        raise HandRefused(f"{fallen.name} is awake: they can hand it over themselves.")
    enc = state.encounter
    if enc is not None and enc.status is EncounterStatus.ACTIVE:
        raise HandRefused(
            "Not in the middle of a fight: help them up first, or wait for it to end."
        )
    return fallen, taker


def loot_events(
    state: GameState,
    taker_id: str,
    from_id: str,
    regs: CharacterRegistries,
    *,
    thing: str | None = None,
    qty: int = 1,
    gold: int = 0,
) -> list[AnyEvent]:
    fallen, taker = _looting(state, taker_id, from_id)
    if (thing is None or qty < 1) and gold < 1:
        raise HandRefused("Nothing to take.")
    events: list[AnyEvent] = []
    if thing is not None and qty >= 1:
        events += _thing_events(fallen, taker, thing, qty, regs, taken=True)
    if gold >= 1:
        events += _gold_events(fallen, taker, gold, taken=True)
    return events
