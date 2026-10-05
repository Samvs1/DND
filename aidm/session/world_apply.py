"""Reducer part for the world events (called only by `aidm.session.reducer.apply`).

Same semantics as the reducer: plain assignment of resolved values, payloads copied on insert,
`ReducerError` for an event that does not fit the state (an engine bug). `event_count` is
incremented by the caller.

Public API: `WorldEvent` (the union of the world events), `WORLD_EVENT_TYPES` (its classes, for
an `isinstance` dispatch), `apply_world_event(state, event)`.
"""

from typing import assert_never

from aidm.models.memory import MAX_NARRATION_LOG
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.models.world_events import (
    AttitudeChanged,
    FactRecorded,
    FeatureDiscovered,
    FeatureIntroduced,
    HostileActPending,
    ItemPlaced,
    ItemRemoved,
    NarrationRecorded,
    NodeDescribed,
    NpcIntroduced,
    PartyMoved,
    QuestUpdated,
    SceneSummarised,
    SecretRevealed,
    ShopOpened,
)
from aidm.session.campaign_apply import refresh_travel
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
    | FeatureDiscovered
    | NodeDescribed
    | ItemPlaced
    | ItemRemoved
    | NarrationRecorded
    | SceneSummarised
)

type SceneEvent = (
    FeatureDiscovered
    | NodeDescribed
    | ItemPlaced
    | ItemRemoved
    | NarrationRecorded
    | SceneSummarised
)

SCENE_EVENT_TYPES = (
    FeatureDiscovered,
    NodeDescribed,
    ItemPlaced,
    ItemRemoved,
    NarrationRecorded,
    SceneSummarised,
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
    FeatureDiscovered,
    NodeDescribed,
    ItemPlaced,
    ItemRemoved,
    NarrationRecorded,
    SceneSummarised,
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
    world.scene_turn = 0
    if event.to_node not in world.visited:
        world.visited.append(event.to_node)
    refresh_travel(state)


def _narrated(state: GameState, text: str, turn: int) -> None:
    memory = state.memory
    if memory.turns_since_summary == 0:
        memory.since_scene = state.world.scene_index
        memory.since_node = state.world.current_node
    memory.turns_since_summary += 1
    memory.narration = [*memory.narration, text][-MAX_NARRATION_LOG:]
    state.world.scene_turn = turn


def _scene_event(state: GameState, event: SceneEvent) -> None:
    world = state.world
    match event:
        case FeatureDiscovered(feature_id=feature_id):
            feature = world.features.get(feature_id)
            if feature is None:
                raise ReducerError(f"unknown feature {feature_id!r}")
            feature.discovered = True
        case NodeDescribed(node_id=node_id, text=text):
            if node_id in world.descriptions:
                raise ReducerError(f"node {node_id!r} is already described")
            world.descriptions[node_id] = text
        case ItemPlaced(item=item):
            if item.id in world.items:
                raise ReducerError(f"duplicate item id {item.id!r}")
            world.items[item.id] = item.model_copy(deep=True)
        case ItemRemoved(item_id=item_id):
            if world.items.pop(item_id, None) is None:
                raise ReducerError(f"unknown item {item_id!r}")
        case NarrationRecorded(text=text, scene_turn=turn):
            _narrated(state, text, turn)
        case SceneSummarised(summary=summary):
            state.memory.summaries.append(summary)
            state.memory.turns_since_summary = 0
        case _:
            assert_never(event)


def apply_world_event(state: GameState, event: WorldEvent) -> None:
    if isinstance(event, SCENE_EVENT_TYPES):
        _scene_event(state, event)
        return
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
