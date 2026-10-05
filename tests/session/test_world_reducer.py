"""Reducer cases for the world events (aidm/session/world_apply.py)."""

import pytest

from aidm.models.memory import MAX_NARRATION_LOG
from aidm.models.state import GameState
from aidm.models.world import Fact, FeatureKind, NpcSecret, Quest, WorldFeature, WorldItem, WorldNpc
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
    SecretRevealed,
    ShopOpened,
)
from aidm.session.reducer import apply, replay
from aidm.session.reducer_errors import ReducerError


def _npc() -> WorldNpc:
    secret = NpcSecret(id="s1", text="hidden")
    return WorldNpc(id="npc-a", name="A", archetype_id="commoner", secrets=[secret])


def test_world_events_apply_and_count() -> None:
    state = GameState(campaign_id="w", seed=1)
    events = [
        NpcIntroduced(npc=_npc()),
        AttitudeChanged(npc_id="npc-a", social=10, deeds=5, hostile=False),
        SecretRevealed(npc_id="npc-a", secret_id="s1"),
        ShopOpened(npc_id="npc-a"),
        QuestUpdated(quest=Quest(id="q", title="Q")),
        FactRecorded(fact=Fact(id="fact-1", text="t", entity_ids=("npc-a",))),
        HostileActPending(actor_id=None, npc_ids=("npc-a",), tool="start_encounter"),
        PartyMoved(from_node=None, to_node="town", scene_index=1),
    ]
    final = replay(state, events)
    npc = final.world.npcs["npc-a"]
    assert (npc.social, npc.deeds, npc.secrets[0].revealed) == (10, 5, True)
    assert final.world.current_node == "town" and final.world.scene_index == 1
    assert final.world.shop_npc_id is None  # moving closes the shop
    assert final.event_count == len(events)
    assert state.world.npcs == {}


def test_world_event_errors() -> None:
    state = GameState(campaign_id="w", seed=1)
    with pytest.raises(ReducerError):
        apply(state, AttitudeChanged(npc_id="ghost", social=0, deeds=0))
    apply(state, NpcIntroduced(npc=_npc()))
    with pytest.raises(ReducerError):
        apply(state, NpcIntroduced(npc=_npc()))
    with pytest.raises(ReducerError):
        apply(state, SecretRevealed(npc_id="npc-a", secret_id="nope"))


def test_scene_events_apply_and_replay() -> None:
    state = GameState(campaign_id="w", seed=1)
    lever = WorldFeature(id="f1", kind=FeatureKind.LEVER, name="lever", hidden=True, discover_dc=5)
    events = [
        FeatureIntroduced(feature=lever),
        FeatureDiscovered(feature_id="f1", creature_id=None),
        NodeDescribed(node_id="town", text="A muddy square."),
        ItemPlaced(item=WorldItem(id="i1", name="key", node_id="town")),
        ItemPlaced(item=WorldItem(id="i2", name="rope", node_id="town")),
        ItemRemoved(item_id="i1"),
        NarrationRecorded(text="You arrive.", scene_turn=1),
    ]
    final = replay(state, events)
    assert final.world.features["f1"].discovered
    assert final.world.descriptions == {"town": "A muddy square."}
    assert list(final.world.items) == ["i2"]
    assert (final.memory.narration, final.world.scene_turn) == (["You arrive."], 1)
    assert final.event_count == len(events)


def test_description_is_stored_once() -> None:
    state = apply(GameState(campaign_id="w", seed=1), NodeDescribed(node_id="t", text="x"))
    with pytest.raises(ReducerError):
        apply(state, NodeDescribed(node_id="t", text="y"))


def test_narration_log_trimmed_and_move_resets_turn() -> None:
    state = GameState(campaign_id="w", seed=1)
    for turn in range(1, MAX_NARRATION_LOG + 4):
        apply(state, NarrationRecorded(text=f"n{turn}", scene_turn=turn))
    assert len(state.memory.narration) == MAX_NARRATION_LOG
    assert state.memory.narration[-1] == f"n{MAX_NARRATION_LOG + 3}"
    apply(state, PartyMoved(from_node=None, to_node="forest", scene_index=1))
    assert state.world.scene_turn == 0


def test_unknown_scene_targets_rejected() -> None:
    state = GameState(campaign_id="w", seed=1)
    with pytest.raises(ReducerError):
        apply(state, FeatureDiscovered(feature_id="nope"))
    with pytest.raises(ReducerError):
        apply(state, ItemRemoved(item_id="nope"))
