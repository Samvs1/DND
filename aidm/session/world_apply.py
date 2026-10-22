"""Reducer part for the world events (called only by `aidm.session.reducer.apply`).

Same semantics as the reducer: plain assignment of resolved values, payloads copied on insert,
`ReducerError` for an event that does not fit the state (an engine bug). `event_count` is
incremented by the caller.

Public API: `WorldEvent` (the union of the world events), `WORLD_EVENT_TYPES` (its classes, for
an `isinstance` dispatch), `apply_world_event(state, event)`. The quest events (M23) are handled
by `aidm.session.quest_apply`, the item-use events (M27.3) by `aidm.session.item_apply`.
"""

from typing import assert_never

from aidm.models.character import Equipped, Keepsake
from aidm.models.memory import MAX_NARRATION_LOG
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.models.world_events import (
    ActionDeclared,
    AttitudeChanged,
    EquipmentChanged,
    FactRecorded,
    FeatureDiscovered,
    FeatureIntroduced,
    HostileActPending,
    ItemDiscovered,
    ItemPlaced,
    ItemRemoved,
    ItemsTraded,
    KeepsakeGained,
    LevelUpReady,
    NarrationRecorded,
    NodeDescribed,
    NpcIntroduced,
    PartyMoved,
    QuestUpdated,
    RewardGranted,
    SceneSummarised,
    SecretRevealed,
    ShopOpened,
)
from aidm.session.campaign_apply import refresh_travel
from aidm.session.item_apply import ITEM_EVENT_TYPES, ItemEvent, apply_item_event, left_place
from aidm.session.quest_apply import (
    QUEST_EVENT_TYPES,
    QuestEvent,
    apply_quest_event,
    quest_updated,
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
    | ItemsTraded
    | RewardGranted
    | LevelUpReady
    | ActionDeclared
    | FeatureDiscovered
    | NodeDescribed
    | ItemPlaced
    | ItemRemoved
    | ItemDiscovered
    | KeepsakeGained
    | NarrationRecorded
    | SceneSummarised
    | EquipmentChanged
    | QuestEvent
    | ItemEvent
)

type SceneEvent = (
    FeatureDiscovered
    | NodeDescribed
    | ItemPlaced
    | ItemRemoved
    | ItemDiscovered
    | NarrationRecorded
    | SceneSummarised
)

SCENE_EVENT_TYPES = (
    FeatureDiscovered,
    NodeDescribed,
    ItemPlaced,
    ItemRemoved,
    ItemDiscovered,
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
    ItemsTraded,
    RewardGranted,
    LevelUpReady,
    ActionDeclared,
    FeatureDiscovered,
    NodeDescribed,
    ItemPlaced,
    ItemRemoved,
    ItemDiscovered,
    KeepsakeGained,
    NarrationRecorded,
    SceneSummarised,
    EquipmentChanged,
    *QUEST_EVENT_TYPES,
    *ITEM_EVENT_TYPES,
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
    world.quest_ask = None  # leaving the node withdraws the giver's question (M23.4)
    left_place(state)  # the alert and the place-scoped gear boons stay behind (M27.3)
    if event.to_node not in world.visited:
        world.visited.append(event.to_node)
    refresh_travel(state)


def _rewarded(state: GameState, kind: str, source: str) -> None:
    """A paid milestone is remembered (`CampaignState.milestones`) so it is never paid twice."""
    campaign = state.campaign
    if kind == "milestone" and campaign is not None and source not in campaign.milestones:
        campaign.milestones.append(source)


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
        case ItemDiscovered(item_id=item_id):
            item = world.items.get(item_id)
            if item is None or not item.hidden:
                raise ReducerError(f"no hidden item {item_id!r}")
            item.hidden = False
        case NarrationRecorded(text=text, scene_turn=turn):
            _narrated(state, text, turn)
        case SceneSummarised(summary=summary):
            state.memory.summaries.append(summary)
            state.memory.turns_since_summary = 0
        case _:
            assert_never(event)


def _equip(state: GameState, creature_id: str, equipped: Equipped, ac: int) -> None:
    creature = state.creatures.get(creature_id)
    if creature is None or creature.pc is None:
        raise ReducerError(f"no hero {creature_id!r} to equip")
    creature.pc.equipped = equipped.model_copy()
    creature.ac = ac


def _keep(state: GameState, creature_id: str, keepsake: Keepsake) -> None:
    creature = state.creatures.get(creature_id)
    if creature is None or creature.pc is None:
        raise ReducerError(f"no hero {creature_id!r} to keep {keepsake.name!r}")
    creature.pc.keepsakes.append(keepsake.model_copy())


def apply_world_event(state: GameState, event: WorldEvent) -> None:
    if isinstance(event, SCENE_EVENT_TYPES):
        _scene_event(state, event)
        return
    if isinstance(event, QUEST_EVENT_TYPES):
        apply_quest_event(state, event)
        return
    if isinstance(event, ITEM_EVENT_TYPES):
        apply_item_event(state, event)
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
            quest_updated(state, quest)
        case FactRecorded(fact=fact):
            world.facts.append(fact)
        case ShopOpened(npc_id=npc_id):
            _npc(state, npc_id)
            world.shop_npc_id = npc_id
        case EquipmentChanged(creature_id=creature_id, equipped=equipped, ac=ac):
            _equip(state, creature_id, equipped, ac)
        case KeepsakeGained(creature_id=creature_id, keepsake=keepsake):
            _keep(state, creature_id, keepsake)
        case RewardGranted(kind=kind, source=source):
            _rewarded(state, kind, source)
        case HostileActPending() | ItemsTraded() | LevelUpReady() | ActionDeclared():
            pass
        case _:
            assert_never(event)
