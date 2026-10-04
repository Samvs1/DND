"""Ability score generation for character creation (SPEC 8, SRD 5.1 "Ability Scores").

Public API:
- `POINT_BUY_BUDGET` (27), `POINT_BUY_COSTS` (SRD "Variant: Customizing Ability Scores" table:
  8 costs 0 ... 13 costs 5, 14 costs 7, 15 costs 9), `POINT_BUY_MIN`/`POINT_BUY_MAX` (8/15).
- `STANDARD_ARRAY`: (15, 14, 13, 12, 10, 8), assigned as a permutation.
- `ABILITY_ROLL_EXPR`: "4d6kh3" (roll four d6, drop the lowest).
- `point_buy_cost(scores) -> int`: total cost; ValueError for a score outside 8..15.
- `roll_ability_scores(rng) -> list[Roll]`: six "4d6kh3" rolls with every die recorded (the
  wizard shows them); the player then assigns the totals.
- `ability_score_errors(choices) -> list[CreationError]`: checks `base_scores` against the method
  (all six present; point buy range and budget; standard array permutation; roll assignment).
- `racial_bonuses(race, subrace, picks) -> dict[Ability, int]`: race + subrace fixed bonuses plus
  `race.ability_choice_bonus` for each picked ability (half-elf).
- `apply_bonuses(base, bonuses) -> dict[Ability, int]`: per-ability sum.
"""

from collections import Counter
from collections.abc import Iterable, Mapping

from aidm.data.race_defs import RaceDef, SubraceDef
from aidm.models.abilities import ABILITIES, Ability
from aidm.models.creation import AbilityMethod, CreationChoices, CreationError, CreationErrorCode
from aidm.models.dice import Roll
from aidm.rules.dice import Rng, roll

POINT_BUY_BUDGET = 27
POINT_BUY_MIN = 8
POINT_BUY_MAX = 15
POINT_BUY_COSTS: dict[int, int] = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
STANDARD_ARRAY: tuple[int, ...] = (15, 14, 13, 12, 10, 8)
ABILITY_ROLL_EXPR = "4d6kh3"
_ROLL_DICE = 4
_ROLL_KEPT = 3
_ROLL_SIDES = 6

_E = CreationErrorCode
_FIELD = "base_scores"


def point_buy_cost(scores: Iterable[int]) -> int:
    total = 0
    for score in scores:
        if score not in POINT_BUY_COSTS:
            raise ValueError(f"point buy score {score} outside {POINT_BUY_MIN}..{POINT_BUY_MAX}")
        total += POINT_BUY_COSTS[score]
    return total


def roll_ability_scores(rng: Rng) -> list[Roll]:
    return [roll(ABILITY_ROLL_EXPR, rng) for _ in ABILITIES]


def _roll_is_valid(item: Roll) -> bool:
    kept = [d.value for d in item.dice if d.kept]
    dropped = [d.value for d in item.dice if not d.kept]
    return (
        item.expression == ABILITY_ROLL_EXPR
        and len(item.dice) == _ROLL_DICE
        and len(kept) == _ROLL_KEPT
        and all(d.sides == _ROLL_SIDES and 1 <= d.value <= _ROLL_SIDES for d in item.dice)
        and item.modifier == 0
        and item.total == sum(kept)
        and all(low <= min(kept) for low in dropped)
    )


def _point_buy_errors(scores: list[int]) -> list[CreationError]:
    bad = [s for s in scores if s not in POINT_BUY_COSTS]
    if bad:
        detail = f"point buy scores must be {POINT_BUY_MIN}..{POINT_BUY_MAX}, got {bad}"
        return [CreationError(code=_E.SCORE_OUT_OF_RANGE, field=_FIELD, detail=detail)]
    cost = point_buy_cost(scores)
    if cost > POINT_BUY_BUDGET:
        detail = f"point buy costs {cost}, budget is {POINT_BUY_BUDGET}"
        return [CreationError(code=_E.POINT_BUY_OVERSPEND, field=_FIELD, detail=detail)]
    return []


def _rolled_errors(scores: list[int], rolls: list[Roll]) -> list[CreationError]:
    if len(rolls) != len(ABILITIES) or not all(_roll_is_valid(r) for r in rolls):
        detail = f"need {len(ABILITIES)} valid {ABILITY_ROLL_EXPR} rolls"
        return [CreationError(code=_E.ROLLS_INVALID, field="rolls", detail=detail)]
    if Counter(scores) != Counter(r.total for r in rolls):
        detail = "scores must be an assignment of the rolled totals"
        return [CreationError(code=_E.ROLL_ASSIGNMENT_MISMATCH, field=_FIELD, detail=detail)]
    return []


def ability_score_errors(choices: CreationChoices) -> list[CreationError]:
    missing = [a.value for a in ABILITIES if a not in choices.base_scores]
    if missing:
        detail = f"missing scores for {missing}"
        return [CreationError(code=_E.ABILITY_MISSING, field=_FIELD, detail=detail)]
    scores = [choices.base_scores[a] for a in ABILITIES]
    match choices.ability_method:
        case AbilityMethod.POINT_BUY:
            return _point_buy_errors(scores)
        case AbilityMethod.STANDARD_ARRAY:
            if sorted(scores) != sorted(STANDARD_ARRAY):
                detail = f"scores must be a permutation of {list(STANDARD_ARRAY)}"
                return [CreationError(code=_E.STANDARD_ARRAY_MISMATCH, field=_FIELD, detail=detail)]
            return []
        case AbilityMethod.ROLL_4D6:
            return _rolled_errors(scores, choices.rolls)


def racial_bonuses(
    race: RaceDef, subrace: SubraceDef | None, picks: Iterable[Ability]
) -> dict[Ability, int]:
    bonuses = dict.fromkeys(ABILITIES, 0)
    fixed = list(race.ability_bonuses) + (list(subrace.ability_bonuses) if subrace else [])
    for entry in fixed:
        bonuses[Ability(entry.ability)] += entry.bonus
    for ability in picks:
        bonuses[ability] += race.ability_choice_bonus
    return bonuses


def apply_bonuses(
    base: Mapping[Ability, int], bonuses: Mapping[Ability, int]
) -> dict[Ability, int]:
    return {a: base[a] + bonuses.get(a, 0) for a in ABILITIES}
