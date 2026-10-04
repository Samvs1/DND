"""Ability score generation: point buy, standard array, 4d6 drop lowest, racial bonuses.

SRD 5.1 "Ability Scores": standard array 15, 14, 13, 12, 10, 8; 4d6 keep the highest three;
the point-buy variant (27 points, scores 8..15, 14 costs 7 and 15 costs 9).
"""

from __future__ import annotations

import random

import pytest

from aidm.data.character_data import character_registries
from aidm.models.abilities import ABILITIES, Ability
from aidm.models.creation import AbilityMethod, CreationChoices, CreationErrorCode
from aidm.models.dice import DieRoll, Roll
from aidm.rules.ability_gen import (
    ABILITY_ROLL_EXPR,
    POINT_BUY_BUDGET,
    ability_score_errors,
    apply_bonuses,
    point_buy_cost,
    racial_bonuses,
    roll_ability_scores,
)

E = CreationErrorCode


def _choices(
    method: AbilityMethod, scores: list[int], rolls: list[Roll] | None = None
) -> CreationChoices:
    return CreationChoices(
        race="human",
        class_index="fighter",
        background="acolyte",
        ability_method=method,
        base_scores=dict(zip(ABILITIES, scores, strict=True)),
        rolls=rolls or [],
    )


def test_golden_point_buy_costs() -> None:
    # SRD 5.1 point-buy table: 15/15/15 + 8/8/8 = 27; 15,14,13,12,10,8 = 9+7+5+4+2+0 = 27.
    assert point_buy_cost([15, 15, 15, 8, 8, 8]) == POINT_BUY_BUDGET
    assert point_buy_cost([15, 14, 13, 12, 10, 8]) == 27
    assert point_buy_cost([8] * 6) == 0
    with pytest.raises(ValueError):
        point_buy_cost([16, 8, 8, 8, 8, 8])


def test_point_buy_valid_and_underspend() -> None:
    assert ability_score_errors(_choices(AbilityMethod.POINT_BUY, [15, 15, 15, 8, 8, 8])) == []
    assert ability_score_errors(_choices(AbilityMethod.POINT_BUY, [10] * 6)) == []


def test_point_buy_overspend() -> None:
    errors = ability_score_errors(_choices(AbilityMethod.POINT_BUY, [15, 15, 15, 15, 8, 8]))
    assert [e.code for e in errors] == [E.POINT_BUY_OVERSPEND]


def test_point_buy_out_of_range() -> None:
    errors = ability_score_errors(_choices(AbilityMethod.POINT_BUY, [16, 8, 8, 8, 8, 8]))
    assert [e.code for e in errors] == [E.SCORE_OUT_OF_RANGE]
    errors = ability_score_errors(_choices(AbilityMethod.POINT_BUY, [7, 8, 8, 8, 8, 8]))
    assert [e.code for e in errors] == [E.SCORE_OUT_OF_RANGE]


def test_standard_array_permutation() -> None:
    ok = _choices(AbilityMethod.STANDARD_ARRAY, [8, 10, 12, 13, 14, 15])
    assert ability_score_errors(ok) == []


def test_standard_array_duplicate_value() -> None:
    bad = _choices(AbilityMethod.STANDARD_ARRAY, [15, 15, 13, 12, 10, 8])
    assert [e.code for e in ability_score_errors(bad)] == [E.STANDARD_ARRAY_MISMATCH]


def test_missing_ability() -> None:
    choices = CreationChoices(
        race="human",
        class_index="fighter",
        background="acolyte",
        ability_method=AbilityMethod.STANDARD_ARRAY,
        base_scores={Ability.STR: 15},
    )
    assert [e.code for e in ability_score_errors(choices)] == [E.ABILITY_MISSING]


def test_roll_4d6_drop_lowest_detail() -> None:
    rolls = roll_ability_scores(random.Random(7))
    assert len(rolls) == 6
    for item in rolls:
        assert item.expression == ABILITY_ROLL_EXPR
        assert len(item.dice) == 4 and sum(d.kept for d in item.dice) == 3
        dropped = next(d.value for d in item.dice if not d.kept)
        assert dropped <= min(d.value for d in item.dice if d.kept)
        assert item.total == sum(d.value for d in item.dice if d.kept)
        assert 3 <= item.total <= 18
    assert rolls == roll_ability_scores(random.Random(7))


def test_rolled_assignment() -> None:
    rolls = roll_ability_scores(random.Random(11))
    totals = [r.total for r in rolls]
    ok = _choices(AbilityMethod.ROLL_4D6, list(reversed(totals)), rolls)
    assert ability_score_errors(ok) == []
    wrong = [*totals[:-1], totals[-1] + 1 if totals[-1] < 18 else 3]
    bad = _choices(AbilityMethod.ROLL_4D6, wrong, rolls)
    assert [e.code for e in ability_score_errors(bad)] == [E.ROLL_ASSIGNMENT_MISMATCH]


def test_forged_roll_rejected() -> None:
    forged = Roll(
        expression=ABILITY_ROLL_EXPR,
        dice=tuple(DieRoll(sides=6, value=6, kept=i < 3) for i in range(4)),
        total=20,
    )
    choices = _choices(AbilityMethod.ROLL_4D6, [20, 3, 3, 3, 3, 3], [forged] * 6)
    assert [e.code for e in ability_score_errors(choices)] == [E.ROLLS_INVALID]
    few = _choices(AbilityMethod.ROLL_4D6, [10] * 6, roll_ability_scores(random.Random(1))[:5])
    assert [e.code for e in ability_score_errors(few)] == [E.ROLLS_INVALID]


def test_golden_racial_bonuses() -> None:
    # SRD 5.1: hill dwarf CON +2 (dwarf) and WIS +1 (hill dwarf); half-elf CHA +2 and two +1s.
    races = character_registries().races
    dwarf = races.get("dwarf")
    bonuses = racial_bonuses(dwarf, dwarf.subraces[0], [])
    assert bonuses[Ability.CON] == 2 and bonuses[Ability.WIS] == 1 and sum(bonuses.values()) == 3
    half_elf = races.get("half-elf")
    bonuses = racial_bonuses(half_elf, None, [Ability.STR, Ability.DEX])
    assert (bonuses[Ability.CHA], bonuses[Ability.STR], bonuses[Ability.DEX]) == (2, 1, 1)
    base = dict.fromkeys(ABILITIES, 10)
    assert apply_bonuses(base, bonuses)[Ability.CHA] == 12
