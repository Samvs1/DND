"""Reducer part for the item-use events (M27.3; called through `aidm.session.world_apply`).

Plain assignment of resolved values; `ReducerError` for an event that does not fit the state.

`FeatureUnlocked` clears the feature's lock (M27.4). `HandedOver` (M29.7a) moves a keepsake from
one hero to the other; an item or gold moves in its `InventoryChanged` / `GoldChanged` pair.

Public API: `ItemEvent` (the union), `ITEM_EVENT_TYPES`, `apply_item_event(state, event)`,
`left_place(state)` (what a `PartyMoved` clears: the alert and the place-scoped boons; a
carried light travels on, M27.12).
"""

from typing import assert_never

from aidm.models.item_events import (
    BoonEnded,
    BoonGained,
    FeatureUnlocked,
    HandedOver,
    ItemUsed,
    ItemUseRefused,
    LightEnded,
    LightLit,
    PlaceAlerted,
    PlacesCharted,
)
from aidm.models.state import GameState
from aidm.models.world import CarriedLight
from aidm.session.reducer_errors import ReducerError

type ItemEvent = (
    ItemUsed
    | ItemUseRefused
    | BoonGained
    | BoonEnded
    | PlaceAlerted
    | PlacesCharted
    | LightLit
    | LightEnded
    | FeatureUnlocked
    | HandedOver
)

ITEM_EVENT_TYPES = (
    ItemUsed,
    ItemUseRefused,
    BoonGained,
    BoonEnded,
    PlaceAlerted,
    PlacesCharted,
    LightLit,
    LightEnded,
    FeatureUnlocked,
    HandedOver,
)


def left_place(state: GameState) -> None:
    world = state.world
    world.alerted = None
    world.alerted_by = None
    world.boons = [b for b in world.boons if b.scope != "place"]


def _used(state: GameState, event: ItemUsed) -> None:
    creature = state.creatures.get(event.creature_id)
    if creature is None or creature.pc is None:
        raise ReducerError(f"no hero {event.creature_id!r} used an item")
    if event.spends_charge:
        entry = next((e for e in creature.pc.inventory if e.item == event.item), None)
        if entry is None:
            raise ReducerError(f"{event.creature_id!r} carries no {event.item!r}")
        entry.charges = event.charges_left
    if event.forage and event.node is not None and event.node not in state.world.foraged:
        state.world.foraged.append(event.node)


def _handed(state: GameState, event: HandedOver) -> None:
    giver = state.creatures.get(event.creature_id)
    taker = state.creatures.get(event.to_id)
    npc = state.world.npcs.get(event.to_id)
    if giver is not None and giver.pc is not None and taker is None and npc is not None:
        if event.gold < 1 or event.item is not None or event.keepsake_id is not None:
            raise ReducerError(f"only gold is paid to {event.to_id!r} this way")
        npc.paid += event.gold  # M29.9a T17: the coins left with the GoldChanged before it
        return
    if giver is None or giver.pc is None or taker is None or taker.pc is None:
        raise ReducerError(f"no heroes {event.creature_id!r} and {event.to_id!r} to hand between")
    if event.keepsake_id is None:
        return
    held = giver.pc.keepsakes
    keepsake = next((k for k in held if k.id == event.keepsake_id), None)
    if keepsake is None:
        raise ReducerError(f"hero {event.creature_id!r} has no keepsake {event.keepsake_id!r}")
    held.remove(keepsake)
    taker.pc.keepsakes.append(keepsake.model_copy())


def apply_item_event(state: GameState, event: ItemEvent) -> None:
    world = state.world
    match event:
        case ItemUsed():
            _used(state, event)
        case BoonGained(boon=boon):
            if boon.creature_id not in state.creatures:
                raise ReducerError(f"no creature {boon.creature_id!r} for the boon")
            kept = [
                b
                for b in world.boons
                if (b.creature_id, b.use_id) != (boon.creature_id, boon.use_id)
            ]
            world.boons = [*kept, boon]
        case BoonEnded(creature_id=cid, use_id=use_id):
            world.boons = [b for b in world.boons if (b.creature_id, b.use_id) != (cid, use_id)]
        case PlaceAlerted(node=node, reason=reason):
            world.alerted = node
            world.alerted_by = reason
        case LightLit(creature_id=cid, item=item, reach=reach):
            if cid not in state.creatures:
                raise ReducerError(f"no bearer {cid!r} for the light")
            kept = [light for light in world.lights if light.creature_id != cid]
            world.lights = [*kept, CarriedLight(creature_id=cid, item=item, reach=reach)]
        case LightEnded(creature_id=cid):
            world.lights = [light for light in world.lights if light.creature_id != cid]
        case PlacesCharted(nodes=nodes):
            world.charted = [*world.charted, *(n for n in nodes if n not in world.charted)]
        case FeatureUnlocked(feature_id=fid):
            feature = world.features.get(fid)
            if feature is None:
                raise ReducerError(f"no feature {fid!r} to unlock")
            feature.lock = None
        case HandedOver():
            _handed(state, event)
        case ItemUseRefused():
            pass
        case _:
            assert_never(event)
