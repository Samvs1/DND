"""M23.6 the campaign writer drafts quests: steps by name, routes, a finale, and repairs (FakeLLM).

Every repair of GOAL_QUESTS "Plan generator and checks" is tested on the sample campaign written
as a model draft (`draft_from_plan`, names instead of ids).
"""

import json
from pathlib import Path
from typing import Any

import pytest

from aidm.dm import campaign_gen
from aidm.dm.campaign_draft import CampaignDraft, assemble_plan
from aidm.dm.campaign_gen import CAMPAIGN_MAX_TOKENS, CampaignSource, generate_campaign
from aidm.dm.fake_llm import FakeReply, fake_tool_call
from aidm.models.campaign import CampaignPlan, RevealKind
from aidm.models.problem import Problem
from aidm.models.quests import QuestStep, RouteKind, StepKind
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.quest_check import check_plan_quests
from aidm.rules.quest_plan import main_quest, main_quests
from tests.ai.campaign_fixtures import draft_from_plan
from tests.ai.fake_scripts import fake_client

PARTY = "four level-1 adventurers: fighter, rogue, cleric, wizard"

# The draft schema is sent with every campaign call (prompt tokens) and shapes the output. The
# pre-M23 schema was ~5.8k characters, with quests ~9k (~2.3k tokens, about a third of the
# candidate list the prompt already carries). 10k characters is the guard: growing past it means
# the draft took on prose fields the engine does not need.
MAX_SCHEMA_CHARS = 10_000


def _assemble(draft: dict[str, Any]) -> tuple[CampaignPlan, list[Problem]]:
    notes: list[Problem] = []
    plan = assemble_plan(CampaignDraft.model_validate(draft), notes)
    assert isinstance(plan, CampaignPlan), plan
    return plan, notes


def _quest(plan: CampaignPlan, title: str) -> Any:
    return next(q for q in plan.quests if q.title == title)


def _messages(notes: list[Problem]) -> str:
    return " | ".join(n.message for n in notes)


def test_full_draft_assembles_with_steps_routes_and_finale() -> None:
    plan, notes = _assemble(draft_from_plan())
    assert notes == [] and check_plan_quests(plan) == []
    assert all(q.steps for q in plan.quests)
    kinds = [[r.kind for r in m.routes] for m in main_quests(plan)]
    assert kinds[1] == [RouteKind.FORCE, RouteKind.PEACE, RouteKind.CUNNING]
    cunning = main_quest(plan, 2).routes[2]
    assert cunning.effect == "boss_surprised" and cunning.hint_npc_id == "corvin-tallowby"
    peace = main_quest(plan, 1).routes[1]
    obtain, deliver = peace.steps
    assert obtain.hidden and obtain.nodes == ("saltcellar-tunnels",)
    assert deliver.npc == boss_npc_id(plan.acts[0].region)
    assert plan.finale is not None and len({o.id for o in plan.finale.options}) == 2


def test_draft_without_quest_parts_still_assembles() -> None:
    plan, notes = _assemble(draft_from_plan(quests=False))
    # M31.1b V16: a quest without steps is no unchecked task: it meets its giver
    meets = [QuestStep(kind=StepKind.MEET, text="-", npc=q.giver_npc_id) for q in plan.quests]
    assert [q.steps[0].model_copy(update={"text": "-"}) for q in plan.quests] == meets
    assert all(len(q.steps) == 1 for q in plan.quests) and plan.finale is None
    assert all(a.main is None for a in plan.acts)
    assert [r.kind for r in main_quest(plan, 1).routes] == [RouteKind.FORCE, RouteKind.PEACE]
    assert [n.subject for n in notes][0] == "finale"


def test_unresolvable_step_becomes_free_with_its_text() -> None:
    draft = draft_from_plan()
    draft["quests"][0]["steps"][1]["npc"] = "Nobody Anyone Knows"
    draft["quests"][1]["steps"][0]["places"] = ["The Dark Lantern Room"]  # an act-3 place
    plan, notes = _assemble(draft)
    # M31.1b V16: the unresolvable step is dropped (nothing could check it); "Recover ..." asks
    # the party to come back, so the ledger quest still ends with Tobin (V14)
    ledger = _quest(plan, "The Missing Ledger").steps
    assert [(s.kind, s.npc) for s in ledger] == [
        (StepKind.CLEAR, None),
        (StepKind.MEET, "tobin-marrow"),
    ]
    smugglers = _quest(plan, "Break the Smugglers").steps
    assert [s.kind for s in smugglers] == [StepKind.MEET]
    assert "became a free step" in _messages(notes)
    assert "a step the engine cannot check" in _messages(notes)
    assert check_plan_quests(plan) == []


def test_giver_in_another_act_moves_the_quest() -> None:
    draft = draft_from_plan()
    signet = next(q for q in draft["quests"] if q["giver"] == "Old Marek Thistlewood")
    signet["act"] = 3
    plan, notes = _assemble(draft)
    assert next(q for q in plan.quests if q.giver_npc_id == "old-marek-thistlewood").act == 2
    assert "moved there" in _messages(notes) and check_plan_quests(plan) == []


def test_moved_quest_over_the_cap_is_dropped_and_its_secret_reveals_friendly() -> None:
    draft = draft_from_plan()
    draft["quests"][0]["act"] = 2  # The Missing Ledger: Tobin lives in act 1
    extra = {"title": "Mend the Nets", "giver": "Dessa Orrin", "objective": "Mend the nets."}
    draft["quests"].append(extra | {"reward_tier": "minor", "act": 1})
    plan, notes = _assemble(draft)
    act1 = [q.title for q in plan.quests if q.act == 1]
    assert act1 == ["Break the Smugglers", "Mend the Nets"]
    assert "dropped" in _messages(notes)
    tobin = next(n for n in plan.npcs if n.name == "Tobin Marrow")
    assert tobin.secrets[0].reveal.kind is RevealKind.ATTITUDE
    assert check_plan_quests(plan) == []


def test_obtain_outside_the_act_is_placed_at_the_first_spoke() -> None:
    draft = draft_from_plan()
    draft["acts"][0]["peace"]["steps"][0]["places"] = ["Cistern of Echoes"]  # act 3
    plan, notes = _assemble(draft)
    obtain = main_quest(plan, 1).routes[1].steps[0]
    assert obtain.kind is StepKind.OBTAIN and obtain.nodes == ("rotting-boathouse",)
    assert "Rotting Boathouse" in _messages(notes)


def test_deliver_without_obtain_gets_one_inserted_or_becomes_free() -> None:
    draft = draft_from_plan()
    kindle = next(q for q in draft["quests"] if q["title"] == "Kindle the Stair")
    kindle["steps"] = kindle["steps"][1:]  # only the deliver is left
    plan, notes = _assemble(draft)
    steps = _quest(plan, "Kindle the Stair").steps
    assert [s.kind for s in steps] == [StepKind.OBTAIN, StepKind.DELIVER]
    assert steps[0].item == steps[1].item and steps[0].nodes == ("cistern-of-echoes",)
    full = [{"kind": "free", "text": f"Ask around ({n})"} for n in range(3)] + kindle["steps"]
    kindle["steps"] = full
    plan, notes = _assemble(draft)
    # M31.1b V16: every unchecked step is dropped; the task left meets its giver
    kept = _quest(plan, "Kindle the Stair").steps
    assert [(s.kind, s.npc) for s in kept] == [(StepKind.MEET, "warden-alder-quill")]
    assert "the step became free" in _messages(notes)
    assert check_plan_quests(plan) == []


def test_lookalike_deliver_item_takes_the_obtained_name() -> None:
    draft = draft_from_plan()
    draft["acts"][0]["peace"]["steps"][1]["item"] = "the Choir tide-orders"
    plan, notes = _assemble(draft)
    obtain, deliver = main_quest(plan, 1).routes[1].steps
    assert deliver.item == obtain.item and notes == []


def test_hint_npc_outside_the_region_is_dropped() -> None:
    draft = draft_from_plan()
    draft["acts"][0]["peace"]["hint_npc"] = "Imre Saltwick"  # lives in act 3
    plan, notes = _assemble(draft)
    assert main_quest(plan, 1).routes[1].hint_npc_id is None
    assert "hint npc" in _messages(notes) and check_plan_quests(plan) == []


def test_missing_finale_or_one_ending_means_no_finale() -> None:
    draft = draft_from_plan()
    draft["finale"]["endings"] = draft["finale"]["endings"][:1]
    plan, notes = _assemble(draft)
    assert plan.finale is None and [n.subject for n in notes] == ["finale"]
    del draft["finale"]
    assert _assemble(draft)[0].finale is None


def test_unplayable_steps_are_repaired() -> None:
    draft = draft_from_plan()
    steps = draft["quests"][0]["steps"]
    steps[0] = {"kind": "clear", "text": "Clear the quay", "places": ["Gullmere Quay"]}
    steps[1] = {"kind": "learn", "text": "Learn the dragon's name", "tag": "dragon"}
    steps.append({"kind": "persuade", "text": "Talk Tobin round"})
    steps.append({"kind": "learn", "text": "Learn of the tunnels", "tag": "Saltcellar"})
    plan, notes = _assemble(draft)
    got = _quest(plan, "The Missing Ledger").steps
    # M31.1b: the unchecked steps are dropped (V16); the giver teaches a side quest's tag when
    # asked (V13a), so "dragon" needs no clue; "saltcellar" only its place teaches, so it is a
    # visit (V13c); "Recover ..." ends with the giver (V14)
    kinds = [StepKind.LEARN, StepKind.VISIT, StepKind.MEET]
    assert [s.kind for s in got] == kinds
    assert (got[0].tag, got[0].item, got[0].text) == ("dragon", None, "Learn about dragon")
    assert (got[1].nodes, got[1].text) == (("saltcellar-tunnels",), "Go to Saltcellar Tunnels")
    assert got[2].npc == "tobin-marrow"
    assert "a step the engine cannot check" in _messages(notes)
    assert check_plan_quests(plan) == []


def test_m29_a_learn_step_may_name_its_clue() -> None:
    """M29.9b T13: "Read the spore-ink note" is a learn step whose clue the engine places."""
    draft = draft_from_plan()
    draft["quests"][0]["steps"][1] = {
        "kind": "learn",
        "text": "Read the note the clerk left",
        "tag": "ledger",
        "item": "Clerk's Note",
        "places": ["Rotting Boathouse"],
        "hidden": True,
    }
    plan, _ = _assemble(draft)
    step = _quest(plan, "The Missing Ledger").steps[1]
    assert (step.kind, step.item, step.nodes, step.hidden) == (
        StepKind.LEARN,
        "Clerk's Note",
        ("rotting-boathouse",),
        True,
    )
    assert step.text == "Learn about ledger from Clerk's Note"
    assert check_plan_quests(plan) == []


def test_cunning_without_effect_and_peace_without_ally_path_are_repaired() -> None:
    draft = draft_from_plan()
    del draft["acts"][1]["cunning"]["effect"]
    del draft["acts"][2]["region"]["boss"]["ally_path"]
    plan, notes = _assemble(draft)
    assert main_quest(plan, 2).routes[2].effect == "boss_alone"
    boss = plan.acts[2].region.boss
    assert boss.ally_path == draft["acts"][2]["peace"]["title"]
    assert len(notes) == 2 and check_plan_quests(plan) == []


def test_draft_schema_stays_compact() -> None:
    size = len(json.dumps(CampaignDraft.model_json_schema()))
    assert size < MAX_SCHEMA_CHARS, size


def _submit(draft: dict[str, Any]) -> FakeReply:
    return fake_tool_call("submit_result", draft)


async def test_generator_accepts_repairs_and_logs_them(tmp_path: Path) -> None:
    draft = draft_from_plan()
    draft["acts"][0]["peace"]["hint_npc"] = "Imre Saltwick"
    client, fake = fake_client(tmp_path, [_submit(draft)])
    result = await generate_campaign("salt", PARTY, client)
    assert result.source is CampaignSource.MODEL and result.attempts == 1
    assert [p.code for p in result.problems] == ["quest_repair"]
    assert fake.requests[0].max_tokens >= CAMPAIGN_MAX_TOKENS


def _left_once(monkeypatch: pytest.MonkeyPatch, times: int) -> None:
    """Quest problems that survive repair on the first `times` checks (repair covers every
    check today, so the generator's policy is tested by stubbing the check)."""
    calls = {"n": 0}
    left = Problem(code="step_tag", message="main-x/peace: tag 'y' can never be learned")

    def fake_check(plan: CampaignPlan) -> list[Problem]:
        calls["n"] += 1
        return [left] if calls["n"] <= times else []

    monkeypatch.setattr(campaign_gen, "check_plan_quests", fake_check)


async def test_generator_retries_on_a_quest_problem_left_after_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _left_once(monkeypatch, 1)
    good = draft_from_plan()
    client, fake = fake_client(tmp_path, [_submit(good), _submit(good)])
    result = await generate_campaign("salt", PARTY, client)
    assert result.source is CampaignSource.MODEL and result.attempts == 2
    assert result.problems == ()
    assert "tag 'y' can never be learned" in str(fake.requests[1].messages[-1]["content"])


async def test_generator_keeps_a_plan_with_only_quest_problems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _left_once(monkeypatch, 1)
    calls = {"n": 0}
    softlock = Problem(code="softlock", message="glutmere: the gateway cannot be reached")

    def rejected_after_first(plan: CampaignPlan, seed: int = 0) -> list[Problem]:
        calls["n"] += 1
        return [] if calls["n"] == 1 else [softlock]

    monkeypatch.setattr(campaign_gen, "plan_problems", rejected_after_first)
    good = draft_from_plan()
    client, _ = fake_client(tmp_path, [_submit(good), _submit(good), _submit(good)])
    result = await generate_campaign("salt", PARTY, client)
    assert result.source is CampaignSource.MODEL and result.attempts == 3
    assert [p.code for p in result.problems] == ["step_tag"]
