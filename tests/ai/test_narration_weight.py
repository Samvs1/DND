"""M19.1 (owner playtest 2026-10-10): the narrator says as much as the beat is worth, does not
retell the place every turn, and cannot tell an outcome the engine did not produce."""

from pathlib import Path
from typing import Any

from aidm.dm.adjudicator import AdjudicationResult, ResolvedCall
from aidm.dm.context import build_context
from aidm.dm.context_text import ContextPurpose
from aidm.dm.guard import check_prose
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narration_weight import (
    FIGHT_JUST_BEGAN,
    NOTHING_CHANGED,
    NarrationWeight,
    max_tokens_for,
    style_for,
    truth_notes,
    weight_for,
)
from aidm.dm.narrator import narrate
from aidm.dm.tool_context import ToolContext
from aidm.models.abilities import Ability, Skill
from aidm.models.checks import CheckKind, CheckResult
from aidm.models.dice import AdvState, D20Roll
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.state import GameState
from aidm.models.world import Fact, Quest, QuestState
from aidm.models.world_events import FactRecorded, QuestUpdated
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import add_npc, party_state, run_tool, tool_call

PLACE = "A leaning guidepost whose letters run like wet ink."


def _check(success: bool) -> CheckResolved:
    roll = D20Roll(rolls=(7,), adv=AdvState.NORMAL, natural=7, modifier=1, total=8)
    result = CheckResult(
        kind=CheckKind.SKILL,
        ability=Ability.INT,
        skill=Skill.INVESTIGATION,
        roll=roll,
        dc=10,
        success=success,
        margin=2 if success else -2,
    )
    return CheckResolved(creature_id="fighter", result=result, reason="looking")


def _quest(state: QuestState) -> QuestUpdated:
    return QuestUpdated(quest=Quest(id="q", title="The Ledger", state=state))


def test_weight_follows_what_happened() -> None:
    fact = FactRecorded(fact=Fact(id="f1", text="A note."))
    assert weight_for([]) is NarrationWeight.MINOR
    assert weight_for([fact]) is NarrationWeight.MINOR  # bookkeeping only
    assert weight_for([_check(False)]) is NarrationWeight.MINOR  # a minor failed try
    assert weight_for([_check(True)]) is NarrationWeight.NORMAL
    assert weight_for([_quest(QuestState.OFFERED)]) is NarrationWeight.NORMAL
    assert weight_for([_quest(QuestState.COMPLETED)]) is NarrationWeight.MAJOR


def test_styles_scale_and_forbid_repetition() -> None:
    minor, major = style_for(NarrationWeight.MINOR), style_for(NarrationWeight.MAJOR)
    assert "1 or 2 short sentences" in minor and "3 to 5 sentences" in major
    for style in (minor, major):
        assert "Narrated:" in style and "never invent loot, gold, wounds" in style
    tokens = [max_tokens_for(w) for w in NarrationWeight]
    assert tokens == sorted(tokens) and tokens[-1] < 700


def test_truth_notes_for_nothing_and_a_fresh_fight() -> None:
    assert truth_notes([]) == [NOTHING_CHANGED]
    assert truth_notes([_check(True)]) == []


async def test_a_turn_with_no_mechanics_is_minor_and_says_nothing_changed(tmp_path: Path) -> None:
    state = party_state()
    result = run_tool(state, "no_mechanics")
    adjudication = AdjudicationResult(
        calls=(ResolvedCall(1, tool_call("no_mechanics"), result),), events=result.events
    )
    client, fake = fake_client(tmp_path)
    await narrate(
        state, adjudication, client, actor_id="fighter", player_text="I pick it up"
    ).collect()
    request = fake.requests[0]
    body = "\n".join(str(m["content"]) for m in request.messages)
    assert style_for(NarrationWeight.MINOR) in body and NOTHING_CHANGED in body
    assert request.max_tokens == max_tokens_for(NarrationWeight.MINOR)


async def test_a_fight_that_only_began_is_told_as_a_standoff(tmp_path: Path) -> None:
    state = party_state()
    add_npc(state, "npc-kern", name="Old Kern", archetype="commoner")
    ctx = ToolContext(actor_id="fighter", confirm_hostile=True)
    result = run_tool(state, "start_encounter", ctx=ctx, against_npcs=["npc-kern"])
    events: list[AnyEvent] = list(result.events)
    assert weight_for(events) is NarrationWeight.MAJOR
    assert FIGHT_JUST_BEGAN in truth_notes(events)


def _with_place(turn: int) -> GameState:
    state = party_state()
    state.world.descriptions["town"] = PLACE
    state.world.scene_turn = turn
    return state


def _text(state: GameState, purpose: ContextPurpose, **kw: Any) -> str:
    return "\n".join(s.text() for s in build_context(state, purpose, "fighter", **kw).sections)


def test_the_narrator_hears_the_place_description_only_on_arrival() -> None:
    assert PLACE in _text(_with_place(0), ContextPurpose.NARRATE)
    assert PLACE not in _text(_with_place(3), ContextPurpose.NARRATE)
    assert PLACE in _text(_with_place(3), ContextPurpose.ADJUDICATE)  # the rules still see it


def test_guard_flags_an_unhurt_npc_told_as_beaten() -> None:
    state = party_state()
    add_npc(state, "npc-kern", name="Old Kern", archetype="commoner")
    report = check_prose("Old Kern lies unconscious in the dust at the post.", state)
    assert [v.kind for v in report.violations] == [ViolationKind.UNHURT_DECLARED_DOWN]
    assert check_prose("Old Kern squints and says nothing.", state).ok


def test_guard_flags_gathered_gold_that_no_event_gave() -> None:
    state = party_state()
    report = check_prose("You gather the scattered gold coin by coin.", state)
    assert ViolationKind.UNEARNED_REWARD in [v.kind for v in report.violations]
