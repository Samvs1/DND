"""request_check, request_save, creative_effect executors and the tier goldens."""

import pytest

from aidm.dm.tool_context import ToolContext
from aidm.models.checks import DcTier
from aidm.models.dm_tiers import Severity, XpTier
from aidm.models.events import CheckResolved, ConditionApplied, DamageTaken, DiceRolled
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.models.world_events import AttitudeChanged, HostileActPending
from aidm.rules.checks import dc_for_tier
from aidm.rules.dm_tiers import (
    item_value_cap,
    party_level,
    severity_damage_dice,
    severity_rounds,
    severity_save_dc,
    xp_award,
)
from tests.ai.tool_fixtures import REGS, add_npc, apply_result, party_state, run_tool


def _with_goblin(state: GameState) -> GameState:
    goblin = Creature(id="goblin-1", name="Goblin", kind=CreatureKind.MONSTER, max_hp=7, hp=7)
    state.creatures[goblin.id] = goblin
    return state


def test_golden_dc_tiers() -> None:
    # SRD 5.1 "Typical Difficulty Classes": 5, 10, 15, 20, 25, 30.
    assert [dc_for_tier(t) for t in DcTier] == [5, 10, 15, 20, 25, 30]


def test_golden_dm_tier_tables() -> None:
    # data/bg3/dm_tiers.json (house numbers, RULES_DECISIONS M4.2).
    tiers = REGS.tiers
    assert severity_damage_dice(tiers, Severity.MINOR, 1) == "1d6"
    assert severity_damage_dice(tiers, Severity.MAJOR, 2) == "3d6"
    assert severity_damage_dice(tiers, Severity.MODERATE, 3) == "2d8"
    assert severity_damage_dice(tiers, Severity.MAJOR, 5) == "5d8"
    assert severity_save_dc(tiers, Severity.MODERATE) == 13
    assert severity_rounds(tiers, Severity.MINOR, 10) == 1
    assert severity_rounds(tiers, Severity.MAJOR, 0) == 1
    assert xp_award(tiers, XpTier.MODERATE, 1) == 75
    assert xp_award(tiers, XpTier.MAJOR, 4) == 1000
    assert [item_value_cap(tiers, t) for t in (1, 2, 3)] == [75, 300, 1500]


def test_request_check_skill_and_ability() -> None:
    state = party_state()
    state.world.region_tier = 2  # M29.6b: act 1 caps a check at medium (DC 15)
    skill = run_tool(
        state, "request_check", actor="rogue", ability_or_skill="stealth", dc_tier="hard"
    )
    assert skill.ok and len(skill.events) == 1
    event = skill.events[0]
    assert isinstance(event, CheckResolved) and event.result.dc == 20
    assert event.result.skill is not None and event.result.skill.value == "stealth"
    ability = run_tool(
        state,
        "request_check",
        actor="fighter",
        ability_or_skill="str",
        dc_tier="easy",
        advantage="advantage",
    )
    assert ability.ok
    check = ability.events[0]
    assert isinstance(check, CheckResolved) and check.result.dc == 10
    assert len(check.result.roll.rolls) == 2  # advantage rolls two d20s


def test_request_check_unknown_actor_is_error() -> None:
    result = run_tool(
        party_state(), "request_check", actor="ghost", ability_or_skill="str", dc_tier="easy"
    )
    assert result.error is not None and "ghost" in result.error
    assert result.events == ()


def test_request_save_many_actors_deduped() -> None:
    result = run_tool(
        party_state(),
        "request_save",
        actors=["fighter", "wizard", "fighter"],
        ability="dex",
        dc_tier="medium",
    )
    assert result.ok
    assert [e.creature_id for e in result.events if isinstance(e, CheckResolved)] == [
        "fighter",
        "wizard",
    ]


def test_creative_damage_uses_tier_dice() -> None:
    state = _with_goblin(party_state())
    result = run_tool(
        state,
        "creative_effect",
        actor="fighter",
        target="goblin-1",
        effect_kind="minor_damage",
        severity="minor",
        damage_type="fire",
    )
    assert result.ok
    rolled = result.events[0]
    assert isinstance(rolled, DiceRolled) and rolled.roll.expression == "1d6"
    assert any(isinstance(e, DamageTaken) for e in result.events)
    assert party_level(state) == 1


def test_creative_condition_save_and_duration_cap() -> None:
    state = _with_goblin(party_state())
    applied = None
    for seed in range(1, 30):
        result = run_tool(
            state,
            "creative_effect",
            seed=seed,
            actor="fighter",
            target="goblin-1",
            effect_kind="condition",
            severity="minor",
            condition="prone",
            duration_rounds=9,
        )
        assert result.ok and isinstance(result.events[0], CheckResolved)
        assert result.events[0].result.dc == 10
        applied = next((e for e in result.events if isinstance(e, ConditionApplied)), None)
        if applied is not None:
            break
    assert applied is not None and applied.condition.rounds_left == 1


def test_creative_condition_not_allowed() -> None:
    result = run_tool(
        _with_goblin(party_state()),
        "creative_effect",
        actor="fighter",
        target="goblin-1",
        effect_kind="condition",
        condition="petrified",
    )
    assert result.error is not None and "condition must be one of" in result.error
    assert result.events == ()


def test_creative_advantage_and_zone_effects() -> None:
    state = party_state()
    adv = run_tool(state, "creative_effect", actor="fighter", effect_kind="advantage_next_attack")
    assert adv.ok and isinstance(adv.events[0], ConditionApplied)
    assert adv.events[0].condition.name == "helped"
    zone = run_tool(state, "creative_effect", actor="fighter", effect_kind="difficult_terrain")
    assert zone.error is not None and "active fight" in zone.error


@pytest.mark.parametrize("kind", ["minor_damage", "condition", "push"])
def test_hostile_creative_effect_on_peaceful_npc_needs_confirm(kind: str) -> None:
    state = party_state()
    add_npc(state)
    result = run_tool(
        state,
        "creative_effect",
        actor="fighter",
        target="npc-mira",
        effect_kind=kind,
        condition="prone",
    )
    assert result.pending is not None and result.pending.npc_ids == ("npc-mira",)
    assert [type(e) for e in result.events] == [HostileActPending]
    confirmed = run_tool(
        state,
        "creative_effect",
        ctx=ToolContext("fighter", True),
        actor="fighter",
        target="npc-mira",
        effect_kind=kind,
        condition="prone",
    )
    assert confirmed.ok
    assert isinstance(confirmed.events[0], AttitudeChanged) and confirmed.events[0].hostile
    apply_result(state, confirmed)
    assert state.world.npcs["npc-mira"].hostile


@pytest.mark.parametrize("kind", ["minor_damage", "condition", "push"])
def test_qa_02_creative_effect_cannot_harm_a_fellow_hero(kind: str) -> None:
    state = party_state()
    hp = state.creatures["wizard"].hp
    result = run_tool(
        state,
        "creative_effect",
        actor="fighter",
        target="wizard",
        effect_kind=kind,
        severity="major",
        condition="prone",
    )
    assert result.error is not None and "fellow hero" in result.error
    assert result.events == ()
    assert state.creatures["wizard"].hp == hp and not state.creatures["wizard"].dead


def test_qa_02_creative_effect_may_still_target_self() -> None:
    result = run_tool(
        party_state(),
        "creative_effect",
        actor="fighter",
        target="fighter",
        effect_kind="minor_damage",
    )
    assert result.ok
