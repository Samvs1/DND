"""M23.1 quest models: step shapes per kind, routes, the finale, world quests and old payloads."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from aidm.models.character import Keepsake
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.quests import (
    FinalePlan,
    MainQuest,
    MainQuestPlan,
    QuestKind,
    QuestStep,
    RouteKind,
    RoutePlan,
    StepKind,
)
from aidm.models.world import ClosedReason, Quest, QuestState, RouteProgress, WorldNpc
from aidm.models.world_events import QuestUpdated

GOOD_STEPS: list[dict[str, Any]] = [
    {"kind": "visit", "text": "Explore", "nodes": ["a", "b", "c"]},
    {"kind": "clear", "text": "Clear the cave", "nodes": ["cave"]},
    {"kind": "defeat", "text": "Defeat the boss", "npc": "boss-r"},
    {"kind": "obtain", "text": "Keystones", "item": "Keystone", "count": 3, "nodes": ["a", "b"]},
    {
        "kind": "obtain",
        "text": "The stone",
        "item": "River-stone",
        "nodes": ["mere"],
        "hidden": True,
    },
    {"kind": "deliver", "text": "Give it back", "item": "River-stone", "npc": "korvell"},
    {"kind": "meet", "text": "Find Yeva", "npc": "yeva"},
    {"kind": "win_over", "text": "Earn trust", "npc": "yeva", "band": "friendly"},
    {"kind": "learn", "text": "Learn the truth", "tag": "bell"},
    {"kind": "free", "text": "Muffle the bell"},
]

BAD_STEPS: list[dict[str, Any]] = [
    {"kind": "visit", "text": "Nowhere"},
    {"kind": "clear", "text": "Two places", "nodes": ["a", "b"]},
    {"kind": "defeat", "text": "Nobody"},
    {"kind": "obtain", "text": "No place", "item": "Keystone"},
    {"kind": "obtain", "text": "Too many places", "item": "Key", "nodes": ["a", "b"]},
    {"kind": "deliver", "text": "To nobody", "item": "Key"},
    {"kind": "meet", "text": "Extra item", "npc": "yeva", "item": "Key"},
    {"kind": "win_over", "text": "Hostile aim", "npc": "yeva", "band": "hostile"},
    {"kind": "win_over", "text": "No band", "npc": "yeva"},
    {"kind": "learn", "text": "No tag"},
    {"kind": "free", "text": "Free with a node", "nodes": ["a"]},
    {"kind": "visit", "text": "Hidden visit", "nodes": ["a"], "hidden": True},
    {"kind": "visit", "text": "Twice", "nodes": ["a", "a"]},
    {"kind": "free", "text": "x" * 101},
]


@pytest.mark.parametrize(
    "raw", GOOD_STEPS, ids=[f"{s['kind']}-{i}" for i, s in enumerate(GOOD_STEPS)]
)
def test_each_step_kind_validates(raw: dict[str, Any]) -> None:
    step = QuestStep.model_validate(raw)
    assert step.kind is StepKind(raw["kind"])


@pytest.mark.parametrize("raw", BAD_STEPS, ids=[f"bad-{i}" for i in range(len(BAD_STEPS))])
def test_wrong_step_fields_are_rejected(raw: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        QuestStep.model_validate(raw)


def test_step_goal_counts() -> None:
    steps = [QuestStep.model_validate(s) for s in GOOD_STEPS]
    assert [s.goal() for s in steps[:4]] == [3, 1, 1, 3]
    assert steps[7].band is AttitudeBand.FRIENDLY


def _free(text: str = "Do it") -> QuestStep:
    return QuestStep(kind=StepKind.FREE, text=text)


def _route(kind: RouteKind, route_id: str, **extra: Any) -> RoutePlan:
    return RoutePlan(id=route_id, kind=kind, title=route_id, steps=(_free(),), **extra)


def test_route_effect_only_on_cunning() -> None:
    _route(RouteKind.CUNNING, "c", effect="boss_alone")
    with pytest.raises(ValidationError):
        _route(RouteKind.CUNNING, "c")
    with pytest.raises(ValidationError):
        _route(RouteKind.PEACE, "p", effect="boss_surprised")


def test_route_needs_one_to_four_steps() -> None:
    with pytest.raises(ValidationError):
        RoutePlan(id="p", kind=RouteKind.PEACE, title="p", steps=())
    with pytest.raises(ValidationError):
        RoutePlan(id="p", kind=RouteKind.PEACE, title="p", steps=(_free(),) * 5)


def test_force_route_is_never_stored() -> None:
    MainQuestPlan(
        routes=(_route(RouteKind.PEACE, "p"), _route(RouteKind.CUNNING, "c", effect="boss_alone"))
    )
    with pytest.raises(ValidationError):
        MainQuestPlan(routes=(_route(RouteKind.FORCE, "f"),))
    with pytest.raises(ValidationError):
        MainQuestPlan(routes=(_route(RouteKind.PEACE, "force"),))
    with pytest.raises(ValidationError):
        MainQuestPlan(routes=(_route(RouteKind.PEACE, "p"), _route(RouteKind.PEACE, "q")))


def test_main_quest_puts_force_first() -> None:
    force = _route(RouteKind.FORCE, "force")
    MainQuest(id="main-r", act=1, title="T", objective="O", routes=(force,))
    with pytest.raises(ValidationError):
        MainQuest(
            id="main-r", act=1, title="T", objective="O", routes=(_route(RouteKind.PEACE, "p"),)
        )


def test_finale_has_two_distinct_endings() -> None:
    option = {"id": "a", "title": "A", "text": "Ending A"}
    FinalePlan.model_validate({"question": "Q?", "options": [option, {**option, "id": "b"}]})
    with pytest.raises(ValidationError):
        FinalePlan.model_validate({"question": "Q?", "options": [option, option]})
    with pytest.raises(ValidationError):
        FinalePlan.model_validate({"question": "Q?", "options": [option]})


def test_world_quest_consistency() -> None:
    Quest(id="q", title="Q", state=QuestState.FAILED, closed_reason=ClosedReason.LEFT_BEHIND)
    with pytest.raises(ValidationError):
        Quest(id="q", title="Q", state=QuestState.ACTIVE, closed_reason=ClosedReason.LEFT_BEHIND)
    with pytest.raises(ValidationError):
        Quest(id="q", title="Q", steps=(_free(),), steps_done=2)
    with pytest.raises(ValidationError):
        Quest(id="q", title="Q", routes=(RouteProgress(route_id="force"),) * 2)


def test_old_quest_payloads_load_as_side_quests() -> None:
    old = '{"type": "quest_updated", "quest": {"id": "q", "title": "Q", "state": "offered"}}'
    quest = QuestUpdated.model_validate_json(old).quest
    assert quest.kind is QuestKind.SIDE and quest.steps == () and quest.routes == ()
    assert quest.objective == "" and quest.log == () and quest.closed_reason is None
    keepsake = Keepsake.model_validate({"id": "k", "name": "Bell-tongue"})
    assert keepsake.quest_id is None
    npc = WorldNpc.model_validate({"id": "n", "name": "N", "archetype_id": "commoner"})
    assert npc.keepsakes == []
