"""M30.1 impossible actions (docs/next/GOAL_IMPOSSIBLE.md): the model may declare an attempt
impossible through `request_check`; the engine rolls no dice, logs `ActionImpossible`, tells the
narrator the verdict, and the guard rejects prose that tells it working. FakeLLM only."""

import random
from pathlib import Path
from typing import Any

from aidm.dm.adjudicator import AdjudicationOptions, AdjudicationResult, ResolvedCall, adjudicate
from aidm.dm.context import SectionKey, build_context
from aidm.dm.context_text import ContextPurpose
from aidm.dm.event_text import event_line, event_notes
from aidm.dm.fake_llm import FakeStream, fake_tool_call
from aidm.dm.guard import check_prose, prose_checker
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narration_templates import template_line
from aidm.dm.narration_weight import NarrationWeight, weight_for
from aidm.dm.narrator import narrate
from aidm.dm.tool_context import ToolContext, ToolResult
from aidm.dm.tools import dm_tools_param
from aidm.models.checks import DcTier
from aidm.models.events import AnyEvent, CheckResolved, DiceRolled
from aidm.models.impossible import ActionImpossible
from aidm.models.state import GameState
from aidm.models.world_events import FeatureIntroduced
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import REGS, party_state, run_tool, tool_call
from tests.unit.rules.item_fixtures import DOCKS, at, hero

HERO = ToolContext(actor_id="hero")
NAT20_SEED = 5  # random.Random(5): the fighter's first d20 is a natural 20 (proved below)
JUMP = "I jump onto the house"
WHY = "a person cannot jump onto a roof"
CHECK: dict[str, Any] = {
    "actor": "fighter",
    "ability_or_skill": "athletics",
    "dc_tier": "nearly_impossible",
    "reason": "jump onto the house",
}
IMPOSSIBLE: dict[str, Any] = {**CHECK, "impossible": WHY}


def _no_dice(events: tuple[AnyEvent, ...] | list[AnyEvent]) -> bool:
    return not any(isinstance(e, CheckResolved | DiceRolled) for e in events)


def _verdict(state: GameState) -> ActionImpossible:
    return ActionImpossible(creature_id="fighter", text="jump onto the house", reason=WHY)


def test_m30_schema_offers_impossible_on_checks_only() -> None:
    check = dm_tools_param(["request_check"])[0]["function"]["parameters"]
    assert "impossible" in check["properties"] and "impossible" not in check["required"]
    assert [t.value for t in DcTier][-1] == "nearly_impossible"  # no seventh DC tier
    save = dm_tools_param(["request_save"])[0]["function"]["parameters"]
    assert "impossible" not in save["properties"]  # DECISIONS M30.1


def test_m30_nat20_still_wins_at_nearly_impossible() -> None:
    state = party_state()
    state.world.region_tier = 4  # no act cap: the tier stays nearly_impossible (DC 30)
    result = run_tool(state, "request_check", seed=NAT20_SEED, **CHECK)
    check = result.events[0]
    assert isinstance(check, CheckResolved)
    assert check.result.roll.natural == 20 and check.result.dc == 30 and check.result.success


def test_m30_executor_returns_the_verdict_with_no_dice() -> None:
    state = party_state()
    result = run_tool(state, "request_check", seed=NAT20_SEED, **IMPOSSIBLE)
    assert result.ok and _no_dice(result.events)
    assert result.events == (_verdict(state),)
    assert "No roll was made" in result.summary and WHY in result.summary


async def test_m30_impossible_ignores_nat20(tmp_path: Path) -> None:
    state = party_state()
    state.world.region_tier = 4
    control = run_tool(state.model_copy(deep=True), "request_check", seed=NAT20_SEED, **CHECK)
    first = control.events[0]
    assert isinstance(first, CheckResolved) and first.result.roll.natural == 20
    script = [fake_tool_call("request_check", IMPOSSIBLE), fake_tool_call("no_mechanics", {})]
    script += [FakeStream(("You leap and land on the roof.",))] * 2
    client, _ = fake_client(tmp_path, script)
    result = await adjudicate(
        state,
        "fighter",
        JUMP,
        client,
        AdjudicationOptions(),
        random.Random(NAT20_SEED),
        REGS,
        lambda e: apply(state, e),
    )
    assert _no_dice(result.events) and result.events == (_verdict(state),)
    assert not result.spends_action
    stream = narrate(state, result, client, actor_id="fighter", player_text=JUMP)
    told = " ".join([chunk.text async for chunk in stream])
    assert "cannot be done" in told and "land on the roof" not in told


def test_m30_event_text_reaches_the_narrator() -> None:
    state = party_state()
    verdict = _verdict(state)
    assert event_line(state, verdict) == f"Fighter cannot do that: {WHY}."
    assert template_line(state, verdict) == f"Fighter tries, but it cannot be done: {WHY}."
    notes = event_notes(state, [verdict])
    assert len(notes) == 1 and "never tell it working" in notes[0]
    pack = build_context(state, ContextPurpose.NARRATE, "fighter", JUMP, events=[verdict])
    events = next(s for s in pack.sections if s.key is SectionKey.EVENTS)
    assert f"Fighter cannot do that: {WHY}." in events.lines
    assert weight_for([verdict]) is NarrationWeight.MINOR


def test_m30_guard_rejects_success_claims() -> None:
    state = party_state()
    events = [_verdict(state)]
    check = prose_checker(state, events, actor_id="fighter", player_text=JUMP)
    for told in (
        "Fighter jumps onto the house.",
        "You jumped and caught the eaves.",
        "Fighter manages to reach the roof.",
        "With a grunt, Fighter lands on the ridge of the roof.",
    ):
        kinds = {v.kind for v in check(told).violations}
        assert ViolationKind.IMPOSSIBLE_DONE in kinds, told
    for honest in (
        "Fighter tries to jump, but the roof is far too high.",
        "Fighter does not jump; the eaves hang well out of reach.",
        "The house looms above, its roof steep and slick with rain.",
    ):
        assert not check(honest).violations, honest
    plain = check_prose("Fighter jumps onto the cart.", state)
    assert ViolationKind.IMPOSSIBLE_DONE not in {v.kind for v in plain.violations}


def test_m30_only_an_impossible_verdict_keeps_the_action() -> None:
    state = party_state()
    alone = run_tool(state, "request_check", **IMPOSSIBLE)
    rolled = run_tool(state, "request_check", **CHECK)
    verdict = ResolvedCall(1, tool_call("request_check", **IMPOSSIBLE), alone)
    check = ResolvedCall(1, tool_call("request_check", **CHECK), rolled)
    refused = ResolvedCall(1, tool_call("request_check", **CHECK), ToolResult(error="no"))
    assert not AdjudicationResult(calls=(verdict,)).spends_action
    assert not AdjudicationResult(calls=(verdict, refused)).spends_action
    assert AdjudicationResult(calls=(verdict, check)).spends_action
    assert AdjudicationResult(calls=(check,)).spends_action


def test_m30_a_lock_check_still_follows_the_lock_rules() -> None:
    """A lock can always be forced or picked: the lock rules win over the AI's verdict."""
    state = at(DOCKS, hero(gear=["crowbar"]))
    made = run_tool(
        state, "introduce_feature", ctx=HERO, kind="container", name="Chest", lock_tier="easy"
    )
    added = made.events[0]
    assert isinstance(added, FeatureIntroduced) and added.feature.lock is not None
    apply(state, added)
    args = {**IMPOSSIBLE, "actor": "hero", "feature": added.feature.id}
    forced = run_tool(state, "request_check", ctx=HERO, seed=3, **args)
    assert forced.ok and any(isinstance(e, CheckResolved) for e in forced.events)
    assert not any(isinstance(e, ActionImpossible) for e in forced.events)
