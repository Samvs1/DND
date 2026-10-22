"""Reducer part for the item-use events (M27.3; called through `aidm.session.world_apply`).

Plain assignment of resolved values; `ReducerError` for an event that does not fit the state.

`FeatureUnlocked` clears the feature's lock (M27.4).

Public API: `ItemEvent` (the union), `ITEM_EVENT_TYPES`, `apply_item_event(state, event)`,
`left_place(state)` (what a `PartyMoved` clears: the alert and the place-scoped boons; a
carried light travels on, M27.12).
"""

from typing import assert_never

from aidm.models.item_events import (
    BoonEnded,
    BoonGained,
    FeatureUnlocked,
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
)


def left_place(state: GameState) -> None:
    world = state.world
    world.alerted = None
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
        case PlaceAlerted(node=node):
            world.alerted = node
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
        case ItemUseRefused():
            pass
        case _:
            assert_never(event)
