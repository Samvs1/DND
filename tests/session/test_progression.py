"""M5.4 progression: travel legality, gateway locks, offers, escape/parley, region resolution."""

from aidm.dm.precheck import BarredIntent, TravelIntent, precheck
from aidm.models.abilities import Skill
from aidm.models.campaign_events import EncounterOffered, OfferResolved, RegionResolved
from aidm.models.campaign_state import OfferChoice, RegionResolution
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world_events import AttitudeChanged, PartyMoved
from aidm.rules.campaign_install import install_campaign
from aidm.rules.finale import choose_events, finale_open
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.progression import campaign_complete, region_resolution_events
from aidm.rules.social import deed_attitude_events
from aidm.session.reducer import replay
from tests.ai.tool_fixtures import run_tool
from tests.session.progression_fixtures import (
    SEED,
    Rigged,
    answer,
    apply_all,
    campaign_state,
    move,
    pending,
    plan,
    win_fight,
)
from tests.sim.sim_setup import build_party

R1 = plan().acts[0].region
R2 = plan().acts[1].region


def _visit_spokes(state: GameState, log: list[AnyEvent]) -> None:
    for spoke in R1.spokes:
        if state.world.current_node != R1.arrival.id:
            move(state, R1.arrival.id, log)
        if move(state, spoke.id, log):
            answer(state, OfferChoice.FIGHT, log)
            win_fight(state, log)


def _no_fight(state: GameState) -> bool:
    return state.encounter is None or state.encounter.status is not EncounterStatus.ACTIVE


def test_travel_follows_legal_neighbours_only() -> None:
    _, state, _ = campaign_state()
    refused = run_tool(state, "move_party", node_id=R1.gateway.id)
    assert refused.error is not None and "not a neighbour" in refused.error
    far = run_tool(state, "move_party", node_id=R2.arrival.id)
    assert far.error is not None
    ok = run_tool(state, "move_party", node_id=R1.spokes[0].id)
    assert ok.ok


def test_gateway_unlocks_only_after_every_spoke() -> None:
    _, state, log = campaign_state()
    move(state, R1.spokes[0].id, log)
    answer(state, OfferChoice.FIGHT, log)
    win_fight(state, log)
    barred = run_tool(state, "move_party", node_id=R1.gateway.id)
    assert barred.error is not None and "barred" in barred.error
    shut = precheck(state, "fighter", f"go to the {R1.gateway.name}")
    assert isinstance(shut, BarredIntent) and "stays shut" in shut.text  # M23.8: it says why
    _visit_spokes(state, log)
    assert R1.gateway.id not in state.world.locked_nodes
    assert R2.arrival.id in state.world.locked_nodes
    intent = precheck(state, "fighter", f"go to the {R1.gateway.name}")
    assert intent == TravelIntent(R1.gateway.id)


def test_offer_appears_once_with_all_options_and_blocks_travel() -> None:
    _, state, log = campaign_state()
    assert state.campaign is not None and state.campaign.offer is None  # arrival is safe
    events = move(state, R1.spokes[0].id, log)
    assert len(events) == 1 and isinstance(events[0], EncounterOffered)
    offer = pending(state)
    assert set(offer.options) == set(OfferChoice)
    assert offer.monster_ids and set(offer.monster_ids) <= set(R1.spokes[0].encounter_themes)
    assert offer.retreat_node == R1.arrival.id and offer.escape_dc == 10
    blocked = run_tool(state, "move_party", node_id=R1.arrival.id)
    assert blocked.error is not None and "parley" in blocked.error
    assert precheck(state, "fighter", f"go to the {R1.arrival.name}") is None


def test_escape_success_retreats_and_never_reoffers() -> None:
    _, state, log = campaign_state()
    move(state, R1.spokes[0].id, log)
    events = answer(state, OfferChoice.ESCAPE, log, rng=Rigged(high=True))
    assert isinstance(events[0], OfferResolved) and events[0].success is True
    assert isinstance(events[-1], PartyMoved) and state.world.current_node == R1.arrival.id
    assert state.encounter is None
    assert move(state, R1.spokes[0].id, log) == []


def test_escape_failure_starts_the_fight() -> None:
    _, state, log = campaign_state()
    move(state, R1.spokes[0].id, log)
    events = answer(state, OfferChoice.ESCAPE, log, rng=Rigged(high=False))
    assert isinstance(events[0], OfferResolved) and events[0].success is False
    assert state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE


def test_surprise_success_surprises_the_foes() -> None:
    _, state, log = campaign_state()
    move(state, R1.spokes[0].id, log)
    answer(state, OfferChoice.SURPRISE, log, rng=Rigged(high=True))
    enc = state.encounter
    assert enc is not None
    assert all(c.surprised == (c.side.value == "hostile") for c in enc.combatants.values())


def test_parley_with_monsters_avoids_or_fails_into_a_fight() -> None:
    _, state, log = campaign_state()
    move(state, R1.spokes[0].id, log)
    answer(state, OfferChoice.PARLEY, log, rng=Rigged(high=True), skill=Skill.INTIMIDATION)
    assert state.encounter is None and state.campaign is not None and state.campaign.offer is None
    move(state, R1.arrival.id, log)
    move(state, R1.spokes[1].id, log)
    answer(state, OfferChoice.PARLEY, log, rng=Rigged(high=False))
    assert state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE


def test_boss_parley_improves_attitude_and_alliance_resolves_region() -> None:
    _, state, log = campaign_state()
    _visit_spokes(state, log)
    move(state, R1.gateway.id, log)
    # M29.6 tuning: the act-1 master parley is an easy Persuasion (DC 10, dm_tiers.json).
    assert pending(state).boss_npc_id == boss_npc_id(R1) and pending(state).parley_dc == 10
    events = answer(state, OfferChoice.PARLEY, log, rng=Rigged(high=True))
    assert any(isinstance(e, AttitudeChanged) for e in events)
    assert _no_fight(state) and region_resolution_events(state) == []
    boss = state.world.npcs[boss_npc_id(R1)]
    apply_all(state, deed_attitude_events(boss, 35, "showed the ledger"), log)
    assert region_resolution_events(state) == []  # talk + one deed: friendly, not an ally
    apply_all(state, deed_attitude_events(boss, 20, "freed his crew"), log)
    resolved = apply_all(state, region_resolution_events(state), log)
    assert isinstance(resolved[0], RegionResolved)
    assert resolved[0].how is RegionResolution.ALLIANCE and not resolved[0].final
    assert R2.arrival.id not in state.world.locked_nodes
    assert move(state, R2.arrival.id, log) == []
    assert state.world.region_tier == 2


def test_boss_defeat_resolves_region_and_offers_no_quests() -> None:
    _, state, log = campaign_state()
    _visit_spokes(state, log)
    assert R2.arrival.id in state.world.locked_nodes
    move(state, R1.gateway.id, log)
    answer(state, OfferChoice.FIGHT, log)
    assert state.world.npcs[boss_npc_id(R1)].hostile
    win_fight(state, log)
    assert state.campaign is not None
    assert state.campaign.resolved == {R1.id: RegionResolution.DEFEAT}
    act2 = {q.id for q in plan().quests if q.act == 2}
    assert not act2 & set(state.world.quests)  # M23.4: the act-2 givers ask on arrival
    assert move(state, R1.arrival.id, log) == []  # the boss no longer waits at the gateway
    move(state, R1.spokes[0].id, log)
    move(state, R1.gateway.id, log)
    assert state.campaign.offer is None


def _tour(state: GameState, log: list[AnyEvent], act: int) -> None:
    region = plan().acts[act].region
    for spoke in region.spokes:
        if state.world.current_node != region.arrival.id:
            move(state, region.arrival.id, log)
        move(state, spoke.id, log)
        answer(state, OfferChoice.FIGHT, log)
        win_fight(state, log)
    move(state, region.gateway.id, log)
    assert pending(state).boss_npc_id == boss_npc_id(region)
    answer(state, OfferChoice.FIGHT, log)
    win_fight(state, log)


def test_full_three_act_progression_reaches_campaign_complete() -> None:
    start, state, log = campaign_state()
    for act in range(3):
        if act:
            move(state, plan().acts[act].region.arrival.id, log)
        _tour(state, log, act)
    assert not campaign_complete(state)  # M23.9: the sample plan ends on the finale choice
    assert finale_open(state) is not None
    finals = [e for e in log if isinstance(e, RegionResolved)]
    assert [e.final for e in finals] == [False, False, True]
    apply_all(state, choose_events(state, "let-it-finish"), log)
    assert campaign_complete(state) and finale_open(state) is None
    assert replay(start, log) == state


def test_a_lair_without_themes_still_gives_the_boss_company() -> None:
    # M20.6 (playtest 3): a generated lair has no themes of its own, so the region boss (a lone
    # acolyte) was a trivial fight. Its company now comes from the region's themes.
    sample = plan()
    act = sample.acts[0]
    gateway = act.region.gateway.model_copy(update={"encounter_themes": ()})
    region = act.region.model_copy(update={"gateway": gateway})
    bare = sample.model_copy(
        update={"acts": (act.model_copy(update={"region": region}), *sample.acts[1:])}
    )
    state = GameState(campaign_id="prog", seed=SEED)
    # M29.6: the boss cap is medium, so at level 1 the bugbear alone fills it; level 2 has room.
    build_party(state, 2)
    log = apply_all(state, install_campaign(state, bare, SEED))
    _visit_spokes(state, log)
    move(state, R1.gateway.id, log)
    offer = pending(state)
    assert offer.boss_npc_id == boss_npc_id(R1) and offer.monster_ids
    # Never trivial; M29.6b boss_budget_scale 0.8 makes the act-1 master's fight easy-to-medium.
    assert offer.difficulty in ("easy", "medium", "hard")
