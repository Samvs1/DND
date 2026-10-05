"""M5.3 install_campaign: registry entries, graph, first move, derived locks, replay."""

import pytest

from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.campaign_events import CampaignInstalled
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.events import AnyEvent, event_adapter
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.models.world_events import PartyMoved
from aidm.rules.campaign_install import boss_npc_id, install_campaign
from aidm.rules.social import attitude_score, band_floor, npc_is_hostile
from aidm.session.reducer import apply, replay
from tests.sim.sim_setup import build_party


def _installed(seed: int = 5) -> tuple[GameState, GameState, list[AnyEvent]]:
    state = GameState(campaign_id="camp", seed=seed)
    build_party(state, 1)
    start = state.model_copy(deep=True)
    events = install_campaign(state, load_sample_campaign(), seed)
    for event in events:
        apply(state, event)
    return start, state, events


def test_install_registers_cast_bosses_quests_and_graph() -> None:
    _, state, events = _installed()
    plan = load_sample_campaign()
    world = state.world
    assert isinstance(events[0], CampaignInstalled) and isinstance(events[-1], PartyMoved)
    assert state.campaign is not None and state.campaign.plan == plan
    arrival = plan.acts[0].region.arrival.id
    assert world.current_node == arrival and world.visited == [arrival]
    assert {n.id for n in plan.npcs} <= set(world.npcs)
    for region in plan.all_regions():
        boss = world.npcs[boss_npc_id(region)]
        assert boss.node_id == region.gateway.id and boss.archetype_id == region.boss.monster_id
        assert npc_is_hostile(boss) is (region.boss.ally_path is None)
    act1 = {q.id for q in plan.quests if q.act == 1}
    assert set(world.quests) == act1
    assert all(q.state is QuestState.OFFERED for q in world.quests.values())
    assert world.node_names[arrival] == plan.acts[0].region.arrival.name
    assert plan.title in world.lore_names
    assert world.region_tier == 1


def test_install_locks_gateway_and_later_acts() -> None:
    _, state, _ = _installed()
    plan = load_sample_campaign()
    r1, r2 = plan.acts[0].region, plan.acts[1].region
    locked = set(state.world.locked_nodes)
    assert r1.gateway.id in locked and r2.arrival.id in locked
    assert not {s.id for s in r1.spokes} & locked
    assert set(state.world.neighbours[r1.arrival.id]) == {s.id for s in r1.spokes}


def test_secrets_carry_structured_reveal_conditions() -> None:
    _, state, _ = _installed()
    odalys = state.world.npcs["odalys-prend"]
    assert odalys.secrets[0].min_score == band_floor(AttitudeBand.FRIENDLY)
    tobin = state.world.npcs["tobin-marrow"]
    assert tobin.secrets[0].min_score is None
    assert tobin.secrets[0].reveal is not None and tobin.secrets[0].reveal.quest_id
    assert attitude_score(odalys) == 0


def test_install_events_replay_and_round_trip() -> None:
    start, state, events = _installed()
    assert replay(start, events) == state
    for event in events:
        assert event_adapter.validate_json(event_adapter.dump_json(event)) == event


def test_install_twice_is_refused() -> None:
    _, state, _ = _installed()
    with pytest.raises(ValueError, match="already installed"):
        install_campaign(state, load_sample_campaign(), 5)
