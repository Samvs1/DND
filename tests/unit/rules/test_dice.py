"""Unit tests for aidm.rules.dice (parser, roller, crit doubling, bounds)."""

from __future__ import annotations

import random

import pytest

from aidm.models.dice import DiceExpr, DiceTerm
from aidm.rules.dice import DiceError, dice_max, dice_min, double_dice, parse_dice, roll


class ScriptedRng:
    """Returns pre-set values in order; records the requested ranges."""

    def __init__(self, values: list[int]) -> None:
        self.values = list(values)
        self.calls: list[tuple[int, int]] = []

    def randint(self, a: int, b: int, /) -> int:
        self.calls.append((a, b))
        return self.values.pop(0)


@pytest.mark.parametrize(
    ("text", "canonical", "modifier", "n_terms"),
    [
        ("1d8", "1d8", 0, 1),
        ("d20", "1d20", 0, 1),
        ("2d6+3", "2d6+3", 3, 1),
        ("2d6 + 3", "2d6+3", 3, 1),
        ("1d4-1", "1d4-1", -1, 1),
        ("2D6+1d4+3", "2d6+1d4+3", 3, 2),
        ("7", "7", 7, 0),
        ("-2", "-2", -2, 0),
        ("0", "0", 0, 0),
        ("1d6+1+2", "1d6+3", 3, 1),
        ("4d6kh3", "4d6kh3", 0, 1),
        ("2d20kl1+5", "2d20kl1+5", 5, 1),
        ("1d100", "1d100", 0, 1),
    ],
)
def test_parse_valid(text: str, canonical: str, modifier: int, n_terms: int) -> None:
    expr = parse_dice(text)
    assert str(expr) == canonical
    assert expr.modifier == modifier
    assert len(expr.terms) == n_terms
    assert parse_dice(canonical) == expr


@pytest.mark.parametrize(
    "text",
    ["", "   ", "abc", "2d", "d", "0d6", "1d1", "1d101", "101d6", "2d6+", "2d6 3",
     "1d6-1d4", "-1d6", "4d6kh5", "4d6kh0", "1d6*2", "2d6 + MOD", "1d6 OR 1d8", "5000"],
)  # fmt: skip
def test_parse_invalid(text: str) -> None:
    with pytest.raises(DiceError):
        parse_dice(text)


def test_dice_error_is_value_error() -> None:
    assert issubclass(DiceError, ValueError)


def test_roll_records_each_die_and_total() -> None:
    rng = ScriptedRng([3, 5, 2])
    result = roll("2d6+1d4+3", rng)
    assert rng.calls == [(1, 6), (1, 6), (1, 4)]
    assert [d.value for d in result.dice] == [3, 5, 2]
    assert [d.sides for d in result.dice] == [6, 6, 4]
    assert result.modifier == 3
    assert result.total == 13
    assert result.expression == "2d6+1d4+3"


def test_roll_constant_consumes_no_rng() -> None:
    rng = ScriptedRng([])
    result = roll("5", rng)
    assert result.total == 5
    assert result.dice == ()


def test_roll_total_may_be_negative() -> None:
    # Raw arithmetic; damage clamping to >= 0 happens at the damage choke point (M1.4).
    assert roll("1d4-3", ScriptedRng([1])).total == -2


def test_keep_highest_drops_lowest() -> None:
    result = roll("4d6kh3", ScriptedRng([2, 6, 2, 5]))
    assert [d.kept for d in result.dice] == [True, True, False, True]  # ties keep the earlier die
    assert result.total == 13


def test_keep_lowest() -> None:
    result = roll("2d20kl1", ScriptedRng([17, 4]))
    assert [d.kept for d in result.dice] == [False, True]
    assert result.total == 4


def test_crit_doubles_dice_not_modifier() -> None:
    # SRD 5.1 "Critical Hits": roll all of the attack's damage dice twice, add modifiers once.
    rng = ScriptedRng([1, 2, 3, 4])
    result = roll("2d6+3", rng, crit=True)
    assert result.expression == "4d6+3"
    assert len(result.dice) == 4
    assert result.total == 1 + 2 + 3 + 4 + 3


def test_double_dice() -> None:
    assert str(double_dice("1d8+1d6-1")) == "2d8+2d6-1"
    assert str(double_dice("7")) == "7"
    assert str(double_dice("4d6kh3")) == "8d6kh6"


def test_bounds() -> None:
    assert (dice_min("2d6+3"), dice_max("2d6+3")) == (5, 15)
    assert (dice_min("4d6kh3"), dice_max("4d6kh3")) == (3, 18)
    assert (dice_min("1d4-3"), dice_max("1d4-3")) == (-2, 1)
    assert (dice_min("-2"), dice_max("-2")) == (-2, -2)


def test_accepts_parsed_expr() -> None:
    expr = DiceExpr(terms=(DiceTerm(count=1, sides=8),), modifier=2)
    assert 3 <= roll(expr, random.Random(1)).total <= 10


def test_golden_greataxe_seeded() -> None:
    # Determinism golden: the same seed always yields the same dice.
    first = roll("1d12+3", random.Random(42))
    second = roll("1d12+3", random.Random(42))
    assert first == second
