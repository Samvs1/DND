"""M23.1 quest plan reading: legacy derivation (GOAL "Old saves"), the sample campaign, the checks.

`plan_weight_of_echoes.json` is the campaign plan of the Slendee playtest save
(c-20261010-161143-6031), extracted once: a plan written before M23 (no steps, no routes).
"""

from __future__ import annotations

import json
from pathlib import Path

from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.campaign import CampaignPlan
from aidm.models.quests import FORCE_ROUTE_ID, MainQuestPlan, QuestKind, RouteKind, StepKind
from aidm.models.world import QuestState
from aidm.rules.plan_ids import boss_npc_id, main_quest_id
from aidm.rules.quest_check import check_plan_quests
from aidm.rules.quest_plan import (
    PEACE_ROUTE_ID,
    main_quest,
    main_quests,
    main_world_quest,
    quest_steps,
    short_text,
    side_world_quest,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "plan_weight_of_echoes.json"


def _old_plan() -> CampaignPlan:
    return CampaignPlan.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_short_text_cuts_at_a_word() -> None:
    assert short_text("a  short   line") == "a short line"
    cut = short_text("word " * 40, 30)
    assert len(cut) <= 30 and cut.endswith("...") and not cut.endswith(" ...")


def test_old_plan_validates_without_quest_fields() -> None:
    plan = _old_plan()
    assert plan.title == "The Weight of Echoes"
    assert plan.finale is None
    assert all(a.main is None for a in plan.acts)
    assert all(q.steps == () for q in plan.quests)


def test_old_plan_derives_a_main_quest_per_act() -> None:
    plan = _old_plan()
    mains = main_quests(plan)
    assert [m.act for m in mains] == [1, 2, 3]
    for act, main in zip(plan.acts, mains, strict=True):
        region = act.region
        assert main.id == main_quest_id(region) == f"main-{region.id}"
        assert (main.title, main.objective) == (act.title, act.goal)
        force, peace = main.routes
        assert force.id == FORCE_ROUTE_ID and force.kind is RouteKind.FORCE
        explore, defeat = force.steps
        assert explore.kind is StepKind.VISIT and explore.nodes == tuple(
            s.id for s in region.spokes
        )
        assert explore.goal() == 3
        assert defeat.kind is StepKind.DEFEAT and defeat.npc == boss_npc_id(region)
        assert peace.id == PEACE_ROUTE_ID and peace.kind is RouteKind.PEACE
        (free,) = peace.steps
        assert free.kind is StepKind.FREE and len(free.text) <= 100
        assert region.boss.ally_path is not None
        assert region.boss.ally_path.startswith(free.text.removesuffix("...")[:40])


def test_old_side_quests_derive_free_then_meet() -> None:
    plan = _old_plan()
    for quest in plan.quests:
        free, meet = quest_steps(plan, quest)
        assert free.kind is StepKind.FREE and free.text == short_text(quest.objective)
        assert meet.kind is StepKind.MEET and meet.npc == quest.giver_npc_id
        assert meet.text.startswith("Return to ")
    world = side_world_quest(plan, plan.quests[0])
    assert world.kind is QuestKind.SIDE and world.state is QuestState.OFFERED
    assert world.objective == plan.quests[0].objective and len(world.steps) == 2


def test_old_plan_checks_report_but_never_reject() -> None:
    codes = {(p.code, p.subject) for p in check_plan_quests(_old_plan())}
    assert ("quest_giver_act", "the-ferrystones") in codes
    assert ("quest_giver_act", "the-knight-s-penance") in codes
    assert ("side_quest_count", "act 1") in codes and ("side_quest_count", "act 2") in codes


def test_main_world_quest_knows_force_from_the_start() -> None:
    quest = main_world_quest(_old_plan(), 2)
    assert quest.kind is QuestKind.MAIN and quest.state is QuestState.ACTIVE
    assert [r.route_id for r in quest.routes] == [FORCE_ROUTE_ID] and quest.steps == ()


def test_sample_campaign_has_steps_routes_and_a_finale() -> None:
    plan = load_sample_campaign()
    assert check_plan_quests(plan) == []
    assert all(q.steps for q in plan.quests)
    kinds = [[r.kind for r in m.routes] for m in main_quests(plan)]
    assert kinds == [
        [RouteKind.FORCE, RouteKind.PEACE],
        [RouteKind.FORCE, RouteKind.PEACE, RouteKind.CUNNING],
        [RouteKind.FORCE, RouteKind.PEACE],
    ]
    cunning = main_quest(plan, 2).routes[2]
    assert cunning.effect == "boss_surprised" and cunning.hint_npc_id is not None
    assert plan.finale is not None and len(plan.finale.options) == 2


def test_stored_peace_route_replaces_the_legacy_one() -> None:
    plan = load_sample_campaign()
    peace = main_quest(plan, 1).routes[1]
    assert peace.id != PEACE_ROUTE_ID and [s.kind for s in peace.steps] == [
        StepKind.OBTAIN,
        StepKind.DELIVER,
    ]
    acts = list(plan.acts)
    acts[0] = acts[0].model_copy(update={"main": MainQuestPlan()})
    legacy = plan.model_copy(update={"acts": tuple(acts)})
    assert main_quest(legacy, 1).routes[1].id == PEACE_ROUTE_ID


def test_checks_catch_bad_step_references() -> None:
    plan = load_sample_campaign()
    quest = plan.quests[0]
    far = quest.steps[0].model_copy(update={"nodes": ("dark-lantern-room",)})
    stranger = quest.steps[1].model_copy(update={"npc": "imre-saltwick"})
    broken = quest.model_copy(update={"steps": (far, stranger)})
    bad = plan.model_copy(update={"quests": (broken, *plan.quests[1:])})
    codes = {p.code for p in check_plan_quests(bad)}
    assert {"step_node", "step_npc"} <= codes


def test_checks_catch_an_item_delivered_but_never_obtained() -> None:
    plan = load_sample_campaign()
    kindle = next(q for q in plan.quests if q.id == "kindle-the-stair")
    deliver = kindle.steps[1]
    lonely = kindle.model_copy(update={"steps": (deliver,)})
    bad = plan.model_copy(
        update={"quests": tuple(lonely if q is kindle else q for q in plan.quests)}
    )
    assert [p.code for p in check_plan_quests(bad)] == ["deliver_item"]
