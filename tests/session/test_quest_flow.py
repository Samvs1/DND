"""M23.2 the engine moves quests: golden walks of sample act 1 (Force and Peace), the one session
helper (`session/quest_flow.settle_after`), no double payout, replay == snapshot, the Slendee plan.
"""

import json
from pathlib import Path

from aidm.dm.event_text import event_line
from aidm.dm.narration_templates import template_line
from aidm.models.campaign import CampaignPlan
from aidm.models.campaign_events import RegionResolved
from aidm.models.campaign_state import OfferChoice, RegionResolution
from aidm.models.character import Keepsake
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import AnyEvent, CreatureDied, event_adapter
from aidm.models.quest_events import KeepsakeGiven, QuestStepDone, RouteDiscovered
from aidm.models.state import GameState
from aidm.models.world import QuestState, RouteProgress
from aidm.models.world_events import KeepsakeGained, PartyMoved, QuestUpdated, RewardGranted
from aidm.rules.campaign_install import install_campaign
from aidm.rules.encounter import end_encounter
from aidm.rules.encounter_offer import arrival_offer_events
from aidm.rules.plan_ids import boss_npc_id, main_quest_id
from aidm.rules.social import AttitudeBand, attitude_band, attitude_score
from aidm.session.quest_flow import settle_after
from aidm.session.reducer import replay
from tests.session.progression_fixtures import (
    DATA,
    REGS,
    answer,
    apply_all,
    campaign_state,
    move,
    plan,
)
from tests.sim.sim_setup import build_party

R1 = plan().acts[0].region
MAIN = main_quest_id(R1)
BOSS = boss_npc_id(R1)
LEDGER = "missing-ledger"
PEACE = "the-tide-orders"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "plan_weight_of_echoes.json"


def _settle(state: GameState, batch: list[AnyEvent], log: list[AnyEvent]) -> list[AnyEvent]:
    return settle_after(state, REGS, batch, lambda events: apply_all(state, events, log))


def _go(state: GameState, node: str, log: list[AnyEvent]) -> list[AnyEvent]:
    mark = len(log)
    move(state, node, log)
    return _settle(state, log[mark:], log)


def _fight_and_win(state: GameState, log: list[AnyEvent]) -> list[AnyEvent]:
    mark = len(log)
    answer(state, OfferChoice.FIGHT, log)
    enc = state.encounter
    assert enc is not None
    for cid, combatant in sorted(enc.combatants.items()):
        if combatant.side is Side.HOSTILE:
            apply_all(state, [CreatureDied(creature_id=cid)], log)
    apply_all(state, end_encounter(state, EncounterStatus.VICTORY), log)
    return _settle(state, log[mark:], log)


def _moved(state: GameState, node: str) -> PartyMoved:
    world = state.world
    return PartyMoved(from_node=world.current_node, to_node=node, scene_index=world.scene_index + 1)


def _started() -> tuple[GameState, GameState, list[AnyEvent]]:
    start, state, log = campaign_state()
    _settle(state, list(log), log)  # the opening resolution after install
    return start, state, log


def _replays(start: GameState, state: GameState, log: list[AnyEvent]) -> None:
    decoded = [event_adapter.validate_json(e.model_dump_json()) for e in log]
    assert replay(start, decoded).model_dump() == state.model_dump()


def _steps(log: list[AnyEvent], quest_id: str) -> list[tuple[str | None, int]]:
    return [
        (e.route_id, e.step) for e in log if isinstance(e, QuestStepDone) and e.quest_id == quest_id
    ]


def test_golden_force_walk_of_act_one() -> None:
    start, state, log = _started()
    main = state.world.quests[MAIN]
    assert main.state is QuestState.ACTIVE and main.routes[0].route_id == "force"
    # the hint NPC Dessa Orrin lives at the arrival: the Peace route is known at once
    assert main.route(PEACE) == RouteProgress(route_id=PEACE)
    ledger = state.world.quests[LEDGER].model_copy(update={"state": QuestState.ACTIVE})
    apply_all(state, [QuestUpdated(quest=ledger)], log)
    for spoke in R1.spokes:
        if state.world.current_node != R1.arrival.id:
            _go(state, R1.arrival.id, log)
        _go(state, spoke.id, log)
        _fight_and_win(state, log)
    assert _steps(log, MAIN) == [("force", 0)]  # every spoke visited
    # tunnels cleared (spoke 2), then Tobin Marrow met back at the docks: done and paid
    assert _steps(log, LEDGER) == [(None, 0), (None, 1)]
    assert state.world.quests[LEDGER].state is QuestState.COMPLETED
    assert len([e for e in log if isinstance(e, RewardGranted) and e.source == LEDGER]) == 1
    _go(state, R1.gateway.id, log)
    won = _fight_and_win(state, log)
    resolved = [e for e in won if isinstance(e, RegionResolved)]
    assert [(e.region_id, e.how) for e in resolved] == [(R1.id, RegionResolution.DEFEAT)]
    main = state.world.quests[MAIN]
    assert main.state is QuestState.COMPLETED
    assert main.log[-1] == "Gorran Hookhand was defeated."
    assert _steps(log, MAIN) == [("force", 0), ("force", 1)]
    _replays(start, state, log)


def test_quest_rewards_are_paid_exactly_once() -> None:
    _, state, log = _started()
    ledger = state.world.quests[LEDGER].model_copy(update={"state": QuestState.ACTIVE})
    apply_all(state, [QuestUpdated(quest=ledger)], log)
    _go(state, "saltcellar-tunnels", log)
    _fight_and_win(state, log)
    _go(state, R1.arrival.id, log)
    for _ in range(3):
        assert _settle(state, [], log) == []
    paid = [e for e in log if isinstance(e, RewardGranted) and e.source == LEDGER]
    assert len(paid) == 1


def test_golden_peace_walk_of_act_one() -> None:
    start, state, log = _started()
    hero = next(cid for cid, c in sorted(state.creatures.items()) if c.pc is not None)
    orders = Keepsake(id="tide-orders", name="Choir tide-orders", quest_id=MAIN)
    apply_all(state, [KeepsakeGained(creature_id=hero, keepsake=orders)], log)
    found = _settle(state, [], log)
    assert [(type(e), getattr(e, "step", None)) for e in found] == [(QuestStepDone, 0)]
    given = KeepsakeGiven(creature_id=hero, keepsake_id="tide-orders", npc_id=BOSS)
    apply_all(state, [given], log)
    allied = _settle(state, [given], log)
    resolved = [e for e in allied if isinstance(e, RegionResolved)]
    assert [(e.region_id, e.how) for e in resolved] == [(R1.id, RegionResolution.ALLIANCE)]
    boss = state.world.npcs[BOSS]
    assert attitude_band(attitude_score(boss)) is AttitudeBand.ALLY and not boss.hostile
    main = state.world.quests[MAIN]
    assert main.state is QuestState.COMPLETED
    assert main.log[-1] == "Gorran Hookhand was won over."
    assert _steps(log, MAIN) == [(PEACE, 0), (PEACE, 1)]
    milestone = [e for e in log if isinstance(e, RewardGranted) and e.source == R1.id]
    assert len(milestone) == 1  # the region milestone, paid once through the alliance
    assert _settle(state, [], log) == []
    _replays(start, state, log)


def test_slendee_plan_main_quest_completes_by_defeat() -> None:
    plan_ = CampaignPlan.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    state = GameState(campaign_id="slendee", seed=3)
    build_party(state, 3)
    start = state.model_copy(deep=True)
    log = apply_all(state, install_campaign(state, plan_, 3))
    region = plan_.acts[0].region
    _settle(state, list(log), log)
    main_id = main_quest_id(region)
    assert state.world.quests[main_id].state is QuestState.ACTIVE
    # the playtest: every corner of the Marches seen, then Brother Molt fought at the abbey
    for node in [*(s.id for s in region.spokes), region.gateway.id]:
        apply_all(state, [_moved(state, node)], log)
    apply_all(state, arrival_offer_events(state, DATA, None), log)
    won = _fight_and_win(state, log)
    assert any(isinstance(e, RegionResolved) for e in won)
    main = state.world.quests[main_id]
    assert main.state is QuestState.COMPLETED
    assert main.log[-1] == f"{region.boss.name} was defeated."
    offered = [q for q in state.world.quests.values() if q.state is QuestState.OFFERED]
    assert offered  # the bulk-offered side quests of old plans stay offered
    _replays(start, state, log)


def test_quest_moments_have_engine_and_template_lines() -> None:
    _, state, log = _started()
    found = next(e for e in log if isinstance(e, RouteDiscovered))
    assert event_line(state, found) == (
        "Quest 'Fog on the Quay': a way the party knows of: Turn Gorran against the Choir."
    )
    assert (
        template_line(state, found)
        == "Another way opens before you: Turn Gorran against the Choir."
    )
    step = QuestStepDone(quest_id=MAIN, route_id="force", step=0, log_line="Explore the quay")
    assert event_line(state, step) == (
        "Quest 'Fog on the Quay': step done: Explore the quay (met by what the party has already"
        " done; describe no new deed for it)."
    )
    assert (
        template_line(state, step) == "Explore the quay: one more part of Fog on the Quay is done."
    )
