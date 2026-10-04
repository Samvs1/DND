"""Property tests for dice, d20 tests and ability arithmetic."""

from __future__ import annotations

import random

from hypothesis import given
from hypothesis import strategies as st

from aidm.models.dice import AdvState
from aidm.rules.abilities import ability_modifier, proficiency_bonus
from aidm.rules.d20 import combine_adv, roll_d20
from aidm.rules.dice import dice_max, dice_min, parse_dice, roll

SIDES = st.sampled_from([2, 3, 4, 6, 8, 10, 12, 20, 100])


@st.composite
def dice_texts(draw: st.DrawFn) -> str:
    n_terms = draw(st.integers(min_value=0, max_value=3))
    parts: list[str] = []
    for _ in range(n_terms):
        count = draw(st.integers(min_value=1, max_value=10))
        sides = draw(SIDES)
        keep = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=count)))
        kind = draw(st.sampled_from(["kh", "kl"]))
        parts.append(f"{count}d{sides}" + ("" if keep is None else f"{kind}{keep}"))
    modifier = draw(st.integers(min_value=-20, max_value=20))
    if not parts:
        return str(modifier)
    text = "+".join(parts)
    if modifier:
        text += f"{modifier:+d}"
    return text


@given(dice_texts(), st.integers(min_value=0, max_value=2**32), st.booleans())
def test_roll_within_bounds(text: str, seed: int, crit: bool) -> None:
    result = roll(text, random.Random(seed), crit=crit)
    expr = parse_dice(result.expression)
    assert dice_min(expr) <= result.total <= dice_max(expr)
    assert result.total == sum(d.value for d in result.dice if d.kept) + result.modifier
    for die in result.dice:
        assert 1 <= die.value <= die.sides


@given(dice_texts())
def test_parse_canonical_round_trip(text: str) -> None:
    expr = parse_dice(text)
    assert parse_dice(str(expr)) == expr


@given(dice_texts(), st.integers(min_value=0, max_value=2**32))
def test_roll_deterministic_for_seed(text: str, seed: int) -> None:
    assert roll(text, random.Random(seed)) == roll(text, random.Random(seed))


@given(
    st.integers(min_value=0, max_value=2**32),
    st.sampled_from(list(AdvState)),
    st.integers(min_value=-10, max_value=20),
    st.integers(min_value=2, max_value=20),
)
def test_d20_bounds_and_determinism(seed: int, adv: AdvState, modifier: int, crit_on: int) -> None:
    r = roll_d20(random.Random(seed), adv, modifier, crit_on=crit_on)
    assert r == roll_d20(random.Random(seed), adv, modifier, crit_on=crit_on)
    assert all(1 <= x <= 20 for x in r.rolls)
    assert len(r.rolls) == (1 if adv is AdvState.NORMAL else 2)
    expected = {AdvState.NORMAL: r.rolls[0], AdvState.ADVANTAGE: max(r.rolls)}
    assert r.natural == expected.get(adv, min(r.rolls))
    assert r.total == r.natural + modifier
    assert r.is_crit == (r.natural >= crit_on)
    assert r.is_fumble == (r.natural == 1)


@given(st.integers(min_value=0, max_value=6), st.integers(min_value=0, max_value=6))
def test_combine_adv_table(adv: int, dis: int) -> None:
    result = combine_adv(adv, dis)
    if adv > 0 and dis > 0 or adv == dis == 0:
        assert result is AdvState.NORMAL
    elif adv > 0:
        assert result is AdvState.ADVANTAGE
    else:
        assert result is AdvState.DISADVANTAGE


@given(st.integers(min_value=1, max_value=29))
def test_modifier_monotonic(score: int) -> None:
    assert 0 <= ability_modifier(score + 1) - ability_modifier(score) <= 1
    assert -5 <= ability_modifier(score) <= 10


@given(st.integers(min_value=1, max_value=19))
def test_proficiency_monotonic(level: int) -> None:
    assert 0 <= proficiency_bonus(level + 1) - proficiency_bonus(level) <= 1
    assert 2 <= proficiency_bonus(level) <= 6
