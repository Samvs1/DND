"""M30.2 impossible actions, the prompt side (docs/next/GOAL_IMPOSSIBLE.md): the adjudicate context
carries the one rule (`context_text.IMPOSSIBLE_RULE`, owner rule: never refuse a physically
possible action) and the hero's spells, and the engine does what each verdict asks: impossible ->
the verdict and no dice; hard but possible -> a high-DC check; magic that allows it -> a normal
resolution. FakeLLM only."""

import random
from pathlib import Path
from typing import Any

from aidm.dm.adjudicator import AdjudicationOptions, AdjudicationResult, adjudicate
from aidm.dm.context import DEFAULT_BUDGET_TOKENS, SectionKey, build_context
from aidm.dm.context_text import IMPOSSIBLE_RULE, ContextPurpose
from aidm.dm.fake_llm import FakeLLM, FakeStep, fake_tool_call
from aidm.models.events import CheckResolved, DiceRolled
from aidm.models.impossible import ActionImpossible
from aidm.models.state import GameState
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import REGS, party_state

LEAP = "I jump straight up from the street onto the roof of the two-storey warehouse"
CLIMB = "I climb the rain-slick warehouse wall up to the roof"
BLINK = "I cast misty step to reach the warehouse roof"
WHY = "no one can jump two storeys straight up"


def _state() -> GameState:
    state = party_state(3)
    state.world.region_tier = 4  # no act cap: a very_hard tier stays DC 25
    wizard = state.creatures["wizard"].pc
    assert wizard is not None
    wizard.spellbook.append("misty-step")
    wizard.prepared.append("misty-step")
    return state


async def _adjudicate(
    tmp_path: Path, state: GameState, actor: str, text: str, script: list[FakeStep]
) -> tuple[AdjudicationResult, FakeLLM]:
    client, fake = fake_client(tmp_path, script)
    result = await adjudicate(
        state,
        actor,
        text,
        client,
        AdjudicationOptions(),
        random.Random(5),
        REGS,
        lambda e: apply(state, e),
    )
    return result, fake


def _system(fake: FakeLLM) -> str:
    return str(fake.requests[0].messages[0]["content"])


def _check(actor: str, skill: str, tier: str, why: str, **extra: Any) -> dict[str, Any]:
    return {"actor": actor, "ability_or_skill": skill, "dc_tier": tier, "reason": why, **extra}


async def test_m30_impossible_gets_the_verdict_and_no_dice(tmp_path: Path) -> None:
    state = _state()
    args = _check("fighter", "athletics", "nearly_impossible", "leap", impossible=WHY)
    script: list[FakeStep] = [fake_tool_call("request_check", args)]
    result, fake = await _adjudicate(tmp_path, state, "fighter", LEAP, script)
    assert IMPOSSIBLE_RULE in _system(fake)  # the model saw the rule on the real path
    assert [type(e) for e in result.events] == [ActionImpossible]
    assert not any(isinstance(e, CheckResolved | DiceRolled) for e in result.events)
    assert not result.fallback and not result.spends_action


async def test_m30_hard_but_possible_gets_a_high_dc_check(tmp_path: Path) -> None:
    state = _state()
    args = _check("fighter", "athletics", "very_hard", "climb the slick wall")
    script: list[FakeStep] = [fake_tool_call("request_check", args)]
    script.append(fake_tool_call("no_mechanics", {}))
    result, _ = await _adjudicate(tmp_path, state, "fighter", CLIMB, script)
    checks = [e for e in result.events if isinstance(e, CheckResolved)]
    assert len(checks) == 1 and checks[0].result.dc == 25  # DC_BY_TIER very_hard
    assert not any(isinstance(e, ActionImpossible) for e in result.events)
    assert result.spends_action


async def test_m30_magic_that_allows_it_resolves_normally(tmp_path: Path) -> None:
    state = _state()
    script: list[FakeStep] = [fake_tool_call("no_mechanics", {})]
    result, fake = await _adjudicate(tmp_path, state, "wizard", BLINK, script)
    party = str(fake.requests[0].messages[1]["content"])
    sheet = next(line for line in party.splitlines() if line.startswith("- Wizard:"))
    assert "Misty Step" in sheet  # the model can see the spell that makes it possible
    assert not any(isinstance(e, ActionImpossible) for e in result.events)
    assert not result.fallback


def test_m30_rule_is_in_the_adjudicate_context_only() -> None:
    state = _state()
    for purpose in ContextPurpose:
        pack = build_context(state, purpose, "fighter", LEAP)
        system = pack.section(SectionKey.SYSTEM)
        assert system is not None
        assert (IMPOSSIBLE_RULE in system.text()) == (purpose is ContextPurpose.ADJUDICATE)
    assert "When unsure, use a check." in IMPOSSIBLE_RULE


def test_m30_adjudicate_context_fits_the_token_budget() -> None:
    state = _state()
    pack = build_context(state, ContextPurpose.ADJUDICATE, "wizard", BLINK)
    assert pack.budget_tokens == DEFAULT_BUDGET_TOKENS
    assert not pack.over_budget and not pack.trimmed  # full sheets, spells included
