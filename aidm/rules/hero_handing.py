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

Public API: `HandRefused(detail)`, `hand_events(...) -> list[AnyEvent]`.
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
    giver: Creature, taker: Creature, thing: str, qty: int, regs: CharacterRegistries
) -> list[AnyEvent]:
    assert giver.pc is not None
    if any(k.id == thing for k in giver.pc.keepsakes):
        return [HandedOver(creature_id=giver.id, to_id=taker.id, keepsake_id=thing)]
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
        HandedOver(creature_id=giver.id, to_id=taker.id, item=thing, qty=qty),
    ]


def _gold_events(giver: Creature, taker: Creature, gold: int) -> list[AnyEvent]:
    assert giver.pc is not None and taker.pc is not None
    if gold > giver.pc.gold:
        raise HandRefused(f"{giver.name} has only {giver.pc.gold} gold.")
    return [
        GoldChanged(creature_id=giver.id, delta=-gold, gold=giver.pc.gold - gold),
        GoldChanged(creature_id=taker.id, delta=gold, gold=taker.pc.gold + gold),
        HandedOver(creature_id=giver.id, to_id=taker.id, gold=gold),
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
