"""Unit tests for aidm.rules.d20 and aidm.rules.abilities."""

from __future__ import annotations

import pytest

from aidm.models.abilities import ABILITIES, Ability
from aidm.models.dice import AdvState
from aidm.rules.abilities import ability_modifier, proficiency_bonus
from aidm.rules.d20 import combine_adv, roll_d20


class ScriptedRng:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def randint(self, a: int, b: int, /) -> int:
        assert (a, b) == (1, 20)
        return self.values.pop(0)


def test_normal_rolls_one_die() -> None:
    r = roll_d20(ScriptedRng([12]), AdvState.NORMAL, 5)
    assert r.rolls == (12,)
    assert (r.natural, r.total, r.is_crit, r.is_fumble) == (12, 17, False, False)


def test_advantage_keeps_higher_and_shows_both() -> None:
    r = roll_d20(ScriptedRng([4, 15]), AdvState.ADVANTAGE, 2)
    assert r.rolls == (4, 15)
    assert (r.natural, r.total) == (15, 17)


def test_disadvantage_keeps_lower() -> None:
    r = roll_d20(ScriptedRng([4, 15]), AdvState.DISADVANTAGE, 2)
    assert (r.natural, r.total) == (4, 6)


def test_nat20_crit_and_nat1_fumble() -> None:
    assert roll_d20(ScriptedRng([20]), modifier=-3).is_crit
    fumble = roll_d20(ScriptedRng([1]), modifier=30)
    assert fumble.is_fumble
    assert not fumble.is_crit


def test_crit_on_19() -> None:
    assert roll_d20(ScriptedRng([19]), crit_on=19).is_crit
    assert not roll_d20(ScriptedRng([19])).is_crit
    with pytest.raises(ValueError):
        roll_d20(ScriptedRng([10]), crit_on=1)


@pytest.mark.parametrize(
    ("adv", "dis", "expected"),
    [
        (0, 0, AdvState.NORMAL),
        (1, 0, AdvState.ADVANTAGE),
        (3, 0, AdvState.ADVANTAGE),
        (0, 1, AdvState.DISADVANTAGE),
        (0, 2, AdvState.DISADVANTAGE),
        (1, 1, AdvState.NORMAL),
        (3, 1, AdvState.NORMAL),  # SRD: many advantages still cancel against one disadvantage
        (1, 4, AdvState.NORMAL),
    ],
)
def test_combine_adv(adv: int, dis: int, expected: AdvState) -> None:
    assert combine_adv(adv, dis) is expected


def test_combine_adv_rejects_negative() -> None:
    with pytest.raises(ValueError):
        combine_adv(-1, 0)


@pytest.mark.parametrize(
    ("score", "mod"),
    [(1, -5), (3, -4), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (15, 2), (20, 5), (30, 10)],
)
def test_golden_ability_modifier(score: int, mod: int) -> None:
    # SRD 5.1 "Ability Scores and Modifiers" table.
    assert ability_modifier(score) == mod


@pytest.mark.parametrize("score", [0, 31, -4])
def test_ability_modifier_out_of_range(score: int) -> None:
    with pytest.raises(ValueError):
        ability_modifier(score)


@pytest.mark.parametrize(
    ("level", "bonus"),
    [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)],
)
def test_golden_proficiency_bonus(level: int, bonus: int) -> None:
    # SRD 5.1 class tables, "Proficiency Bonus" column.
    assert proficiency_bonus(level) == bonus


@pytest.mark.parametrize("level", [0, 21])
def test_proficiency_bonus_out_of_range(level: int) -> None:
    with pytest.raises(ValueError):
        proficiency_bonus(level)


def test_ability_values_match_srd_index() -> None:
    assert [a.value for a in ABILITIES] == ["str", "dex", "con", "int", "wis", "cha"]
    assert Ability("dex") is Ability.DEX
