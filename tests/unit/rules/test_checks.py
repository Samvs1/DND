"""Unit and golden tests for aidm.rules.checks (skills, checks, saves, passives, DC tiers).

Golden numbers come from SRD 5.1 (CC-BY-4.0) as vendored in data/srd (5e-bits 2014).
"""

from __future__ import annotations

import pytest

from aidm.data.srd import srd
from aidm.models.abilities import SKILL_ABILITY, Ability, Skill
from aidm.models.checks import CheckKind, CheckResult, DcTier
from aidm.models.dice import AdvState
from aidm.models.events import CheckResolved, event_adapter
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.checks import (
    ability_check,
    dc_for_tier,
    passive_score,
    save_bonus,
    saving_throw,
    skill_bonus,
    skill_check,
)
from aidm.session.reducer import apply


class ScriptedRng:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def randint(self, a: int, b: int, /) -> int:
        assert (a, b) == (1, 20)
        return self.values.pop(0)


def goblin() -> Creature:
    # SRD 5.1 Goblin: DEX 14, WIS 8, PB +2, Stealth +6, passive Perception 9.
    return Creature(
        id="gob",
        name="Goblin",
        kind=CreatureKind.MONSTER,
        abilities={Ability.STR: 8, Ability.DEX: 14, Ability.CON: 10,
                   Ability.INT: 10, Ability.WIS: 8, Ability.CHA: 8},
        max_hp=7,
        hp=7,
        skill_expertise=[Skill.STEALTH],
    )  # fmt: skip


def red_dragon() -> Creature:
    # SRD 5.1 Adult Red Dragon: DEX 10, CON 25, WIS 13, PB +6; saves Dex +6, Con +13;
    # Perception +13 (passive 23), Stealth +6.
    return Creature(
        id="drag",
        name="Adult Red Dragon",
        kind=CreatureKind.MONSTER,
        abilities={Ability.STR: 27, Ability.DEX: 10, Ability.CON: 25,
                   Ability.INT: 16, Ability.WIS: 13, Ability.CHA: 21},
        max_hp=256,
        hp=256,
        proficiency_bonus=6,
        save_proficiencies=[Ability.DEX, Ability.CON, Ability.WIS, Ability.CHA],
        skill_proficiencies=[Skill.STEALTH, Skill.PERCEPTION],
        skill_expertise=[Skill.PERCEPTION],
    )  # fmt: skip


def test_skill_ability_matches_srd_data() -> None:
    srd_map = {s.index: s.ability_score.index for s in srd().skills.all()}
    assert len(Skill) == 18
    assert {s.value: a.value for s, a in SKILL_ABILITY.items()} == srd_map


def test_golden_dc_tiers() -> None:
    # SRD 5.1 "Typical Difficulty Classes": 5, 10, 15, 20, 25, 30.
    expected = [5, 10, 15, 20, 25, 30]
    assert [dc_for_tier(t) for t in DcTier] == expected


def test_golden_goblin_stealth_and_passive_perception() -> None:
    gob = goblin()
    assert skill_bonus(gob, Skill.STEALTH) == 6  # SRD Goblin: Stealth +6 (expertise)
    assert passive_score(gob, Skill.PERCEPTION) == 9  # SRD Goblin: passive Perception 9
    assert skill_bonus(gob, Skill.ATHLETICS) == -1


def test_golden_adult_red_dragon_saves_and_skills() -> None:
    d = red_dragon()
    assert save_bonus(d, Ability.DEX) == 6  # SRD: Dex +6
    assert save_bonus(d, Ability.CON) == 13  # SRD: Con +13
    assert save_bonus(d, Ability.STR) == 8  # not proficient: STR 27 -> +8
    assert skill_bonus(d, Skill.PERCEPTION) == 13  # SRD: Perception +13
    assert skill_bonus(d, Skill.STEALTH) == 6  # SRD: Stealth +6
    assert passive_score(d, Skill.PERCEPTION) == 23  # SRD: passive Perception 23


def test_passive_adv_and_disadv_shift_by_five() -> None:
    # SRD 5.1 "Passive Checks": +5 with advantage, -5 with disadvantage.
    gob = goblin()
    assert passive_score(gob, Skill.PERCEPTION, AdvState.ADVANTAGE) == 14
    assert passive_score(gob, Skill.PERCEPTION, AdvState.DISADVANTAGE) == 4
    assert passive_score(gob, Skill.PERCEPTION, bonus=2) == 11


def test_skill_check_result_fields() -> None:
    r = skill_check(ScriptedRng([10]), goblin(), Skill.STEALTH, 15)
    assert (r.kind, r.ability, r.skill) == (CheckKind.SKILL, Ability.DEX, Skill.STEALTH)
    assert (r.roll.total, r.dc, r.success, r.margin) == (16, 15, True, 1)
    r = skill_check(ScriptedRng([8]), goblin(), Skill.STEALTH, 15)
    assert (r.success, r.margin) == (False, -1)


def test_check_meets_dc_exactly_succeeds() -> None:
    r = ability_check(ScriptedRng([12]), goblin(), Ability.DEX, 14)
    assert r.success and r.margin == 0 and r.skill is None


def test_check_nat20_and_nat1_are_automatic() -> None:
    hi = ability_check(ScriptedRng([20]), goblin(), Ability.WIS, 30)
    assert hi.success and hi.margin == 19 - 30
    lo = skill_check(ScriptedRng([1]), red_dragon(), Skill.PERCEPTION, 5)
    assert not lo.success and lo.margin == 14 - 5


def test_saves_use_total_only() -> None:
    d = red_dragon()
    nat20 = saving_throw(ScriptedRng([20]), d, Ability.DEX, 30)
    assert nat20.kind is CheckKind.SAVE and not nat20.success
    nat1 = saving_throw(ScriptedRng([1]), d, Ability.CON, 10)
    assert nat1.success and nat1.roll.total == 14


def test_advantage_and_bonus_pass_through() -> None:
    r = saving_throw(
        ScriptedRng([3, 17]), goblin(), Ability.WIS, 15, adv=AdvState.ADVANTAGE, bonus=2
    )
    assert r.roll.rolls == (3, 17) and r.roll.total == 18 and r.success


def test_negative_dc_rejected() -> None:
    with pytest.raises(ValueError):
        ability_check(ScriptedRng([10]), goblin(), Ability.STR, -1)


def test_check_resolved_event_is_log_only() -> None:
    state = GameState(campaign_id="c", seed=1)
    result = skill_check(ScriptedRng([10]), goblin(), Skill.STEALTH, 15)
    event = CheckResolved(creature_id="gob", result=result, reason="sneak past")
    assert event_adapter.validate_json(event_adapter.dump_json(event)) == event
    apply(state, event)
    assert state.event_count == 1 and state.creatures == {}
    assert isinstance(event.result, CheckResult)
