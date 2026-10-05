"""Reducer part for the world events (called only by `aidm.session.reducer.apply`).

Same semantics as the reducer: plain assignment of resolved values, payloads copied on insert,
`ReducerError` for an event that does not fit the state (an engine bug). `event_count` is
incremented by the caller.

Public API: `WorldEvent` (the union of the world events), `WORLD_EVENT_TYPES` (its classes, for
an `isinstance` dispatch), `apply_world_event(state, event)`.
"""

from typing import assert_never

from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.models.world_events import (
    AttitudeChanged,
    FactRecorded,
    FeatureIntroduced,
    HostileActPending,
    NpcIntroduced,
    PartyMoved,
    QuestUpdated,
    SecretRevealed,
    ShopOpened,
)
from aidm.session.reducer_errors import ReducerError

type WorldEvent = (
    NpcIntroduced
    | FeatureIntroduced
    | AttitudeChanged
    | SecretRevealed
    | PartyMoved
    | QuestUpdated
    | FactRecorded
    | ShopOpened
    | HostileActPending
)

WORLD_EVENT_TYPES = (
    NpcIntroduced,
    FeatureIntroduced,
    AttitudeChanged,
    SecretRevealed,
    PartyMoved,
    QuestUpdated,
    FactRecorded,
    ShopOpened,
    HostileActPending,
)


def _npc(state: GameState, npc_id: str) -> WorldNpc:
    npc = state.world.npcs.get(npc_id)
    if npc is None:
        raise ReducerError(f"unknown npc {npc_id!r}")
    return npc


def _reveal(npc: WorldNpc, secret_id: str) -> None:
    for secret in npc.secrets:
        if secret.id == secret_id:
            secret.revealed = True
            return
    raise ReducerError(f"npc {npc.id!r} has no secret {secret_id!r}")


def _moved(state: GameState, event: PartyMoved) -> None:
    world = state.world
    world.current_node = event.to_node
    world.scene_index = event.scene_index
    world.shop_npc_id = None
    if event.to_node not in world.visited:
        world.visited.append(event.to_node)


def apply_world_event(state: GameState, event: WorldEvent) -> None:
    world = state.world
    match event:
        case NpcIntroduced(npc=npc):
            if npc.id in world.npcs:
                raise ReducerError(f"duplicate npc id {npc.id!r}")
            world.npcs[npc.id] = npc.model_copy(deep=True)
        case FeatureIntroduced(feature=feature):
            if feature.id in world.features:
                raise ReducerError(f"duplicate feature id {feature.id!r}")
            world.features[feature.id] = feature.model_copy(deep=True)
        case AttitudeChanged(npc_id=npc_id, social=social, deeds=deeds, hostile=hostile):
            npc = _npc(state, npc_id)
            npc.social, npc.deeds, npc.hostile = social, deeds, hostile
        case SecretRevealed(npc_id=npc_id, secret_id=secret_id):
            _reveal(_npc(state, npc_id), secret_id)
        case PartyMoved():
            _moved(state, event)
        case QuestUpdated(quest=quest):
            world.quests[quest.id] = quest
        case FactRecorded(fact=fact):
            world.facts.append(fact)
        case ShopOpened(npc_id=npc_id):
            _npc(state, npc_id)
            world.shop_npc_id = npc_id
        case HostileActPending():
            pass
        case _:
            assert_never(event)
