"""Reducer cases for the world events (aidm/session/world_apply.py)."""

import pytest

from aidm.models.state import GameState
from aidm.models.world import Fact, NpcSecret, Quest, WorldNpc
from aidm.models.world_events import (
    AttitudeChanged,
    FactRecorded,
    HostileActPending,
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
