"""M23.1 quest events: reducer semantics, replay == snapshot, the old Slendee plan installing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidm.models.campaign import CampaignPlan
from aidm.models.character import Keepsake
from aidm.models.events import AnyEvent, event_adapter
from aidm.models.quest_events import KeepsakeGiven, QuestLeadAdded, QuestStepDone, RouteDiscovered
from aidm.models.quests import FORCE_ROUTE_ID, QuestKind, StepKind
from aidm.models.state import GameState
from aidm.models.world import MAX_QUEST_LOG, QuestLead, QuestState
from aidm.models.world_events import KeepsakeGained, QuestUpdated
from aidm.rules.campaign_install import install_campaign
from aidm.rules.quest_plan import main_quests, main_world_quest, side_world_quest
from aidm.session.reducer import apply, replay
from aidm.session.reducer_errors import ReducerError
from tests.sim.sim_setup import build_party

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "plan_weight_of_echoes.json"


def _installed() -> tuple[GameState, GameState, list[AnyEvent]]:
    plan = CampaignPlan.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    state = GameState(campaign_id="slendee", seed=3)
    build_party(state, 1)
    start = state.model_copy(deep=True)
    events = install_campaign(state, plan, 3)
    for event in events:
        apply(state, event)
    return start, state, events


def _run(state: GameState, events: list[AnyEvent]) -> None:
    for event in events:
        apply(state, event)


def test_old_plan_installs_with_derived_side_quest_steps() -> None:
    _, state, _ = _installed()
    assert state.campaign is not None
    plan = state.campaign.plan
    act1 = [q for q in plan.quests if q.act == 1]
    assert set(state.world.quests) == {q.id for q in act1}
    for quest in state.world.quests.values():
        assert quest.kind is QuestKind.SIDE and quest.state is QuestState.OFFERED
        assert [s.kind for s in quest.steps] == [StepKind.FREE, StepKind.MEET]
    assert len(main_quests(plan)) == 3


def _quest_log(state: GameState) -> list[AnyEvent]:
    assert state.campaign is not None
    plan = state.campaign.plan
    hero = next(iter(state.creatures))
    keepsake = Keepsake(
        id="bell-tongue", name="False Bell-Tongue", quest_id="a-bell-s-false-tongue"
    )
    return [
        QuestUpdated(quest=main_world_quest(plan, 1)),
        RouteDiscovered(quest_id="main-thornveil-marches", route_id="peace"),
        QuestStepDone(quest_id="main-thornveil-marches", route_id=FORCE_ROUTE_ID, step=0),
        QuestStepDone(quest_id="a-bell-s-false-tongue", step=0, log_line="The bell is muffled."),
        QuestLeadAdded(lead=QuestLead(quest_id="the-man-in-the-runnel", text="Someone needs help")),
        KeepsakeGained(creature_id=hero, keepsake=keepsake),
        KeepsakeGiven(creature_id=hero, keepsake_id="bell-tongue", npc_id="yeva-mossbell"),
    ]


def test_quest_events_apply_and_replay_equals_snapshot() -> None:
    start, state, install = _installed()
    events = _quest_log(state)
    _run(state, events)
    main = state.world.quests["main-thornveil-marches"]
    assert [(r.route_id, r.steps_done) for r in main.routes] == [("force", 1), ("peace", 0)]
    bell = state.world.quests["a-bell-s-false-tongue"]
    assert bell.steps_done == 1 and bell.log == ("The bell is muffled.",)
    assert [lead.quest_id for lead in state.world.leads] == ["the-man-in-the-runnel"]
    hero = state.creatures[next(iter(state.creatures))]
    assert hero.pc is not None and hero.pc.keepsakes == []
    assert [k.id for k in state.world.npcs["yeva-mossbell"].keepsakes] == ["bell-tongue"]
    decoded = [event_adapter.validate_json(e.model_dump_json()) for e in install + events]
    assert replay(start, decoded).model_dump() == state.model_dump()
    assert GameState.model_validate_json(state.model_dump_json()) == state


@pytest.mark.parametrize(
    "bad",
    [
        QuestStepDone(quest_id="a-bell-s-false-tongue", step=1),
        QuestStepDone(quest_id="nope", step=0),
        QuestStepDone(quest_id="a-bell-s-false-tongue", route_id="peace", step=0),
        RouteDiscovered(quest_id="nope", route_id="peace"),
        KeepsakeGiven(creature_id="fighter", keepsake_id="nothing", npc_id="yeva-mossbell"),
    ],
    ids=["skip-a-step", "unknown-quest", "unknown-route", "route-unknown-quest", "no-keepsake"],
)
def test_events_that_do_not_fit_are_reducer_errors(bad: AnyEvent) -> None:
    _, state, _ = _installed()
    with pytest.raises(ReducerError):
        apply(state, bad)


def test_steps_stop_at_the_end_and_routes_are_known_once() -> None:
    _, state, _ = _installed()
    assert state.campaign is not None
    _run(state, [QuestUpdated(quest=main_world_quest(state.campaign.plan, 1))])
    with pytest.raises(ReducerError):
        apply(state, RouteDiscovered(quest_id="main-thornveil-marches", route_id=FORCE_ROUTE_ID))
    quest_id = "a-bell-s-false-tongue"
    _run(
        state, [QuestStepDone(quest_id=quest_id, step=0), QuestStepDone(quest_id=quest_id, step=1)]
    )
    with pytest.raises(ReducerError):
        apply(state, QuestStepDone(quest_id=quest_id, step=2))
    lead = QuestLeadAdded(lead=QuestLead(quest_id="x", text="A lead"))
    apply(state, lead)
    with pytest.raises(ReducerError):
        apply(state, lead)


def test_quest_log_keeps_the_last_lines() -> None:
    _, state, _ = _installed()
    assert state.campaign is not None
    plan = state.campaign.plan
    _run(state, [QuestUpdated(quest=main_world_quest(plan, 1))])
    for step in range(2):
        line = f"line {step}"
        apply(
            state,
            QuestStepDone(
                quest_id="main-thornveil-marches", route_id="force", step=step, log_line=line
            ),
        )
    long_log = tuple(f"old {i}" for i in range(MAX_QUEST_LOG))
    side = side_world_quest(plan, plan.quests[0]).model_copy(update={"log": long_log})
    _run(state, [QuestUpdated(quest=side), QuestStepDone(quest_id=side.id, step=0, log_line="new")])
    assert state.world.quests[side.id].log == (*long_log[1:], "new")
    assert state.world.quests["main-thornveil-marches"].log == ("line 0", "line 1")
