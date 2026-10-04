"""Ability checks, skill checks, saving throws, passive scores and the DC tier map.

Public API:
- `DC_BY_TIER` / `dc_for_tier(tier) -> int`: SRD 5.1 "Typical Difficulty Classes" table
  (very easy 5, easy 10, medium 15, hard 20, very hard 25, nearly impossible 30); the AI picks a
  `DcTier`, the engine owns the number (SPEC 6.3).
- `skill_bonus(creature, skill) -> int`: governing ability modifier + proficiency bonus when
  proficient, doubled with expertise (SRD 5.1 "Proficiency Bonus", Rogue "Expertise").
- `save_bonus(creature, ability) -> int`: ability modifier + proficiency bonus when proficient.
- `ability_check`, `skill_check`, `saving_throw(rng, creature, ..., dc, *, adv, bonus)`:
  roll one d20 test and return a `CheckResult`. `bonus` carries situational modifiers from
  callers (Guidance, Bless, Jack of All Trades); `adv` is the already-combined advantage state.
  Ability and skill checks: a natural 20 always succeeds and a natural 1 always fails (BG3).
  Saving throws: the total against the DC only (SRD 5.1). See docs/RULES_DECISIONS.md.
- `passive_score(creature, skill, adv=NORMAL, bonus=0) -> int`: SRD 5.1 "Passive Checks":
  10 + all modifiers that normally apply, +5 with advantage, -5 with disadvantage.

Logging: these functions return results, not events. The caller logs a `CheckResolved` event
with the result (and emits any consequences as their own events).
"""

from aidm.models.abilities import SKILL_ABILITY, Ability, Skill
from aidm.models.checks import CheckKind, CheckResult, DcTier
from aidm.models.dice import AdvState, D20Roll
from aidm.models.state import Creature
from aidm.rules.abilities import ability_modifier
from aidm.rules.d20 import roll_d20
from aidm.rules.dice import Rng

DC_BY_TIER: dict[DcTier, int] = {
    DcTier.TRIVIAL: 5,
    DcTier.EASY: 10,
    DcTier.MEDIUM: 15,
    DcTier.HARD: 20,
    DcTier.VERY_HARD: 25,
    DcTier.NEARLY_IMPOSSIBLE: 30,
}

PASSIVE_BASE = 10
PASSIVE_ADV_SHIFT = 5


def dc_for_tier(tier: DcTier) -> int:
    return DC_BY_TIER[tier]


def _mod(creature: Creature, ability: Ability) -> int:
    return ability_modifier(creature.abilities[ability])


def skill_bonus(creature: Creature, skill: Skill) -> int:
    pb = creature.proficiency_bonus
    if skill in creature.skill_expertise:
        prof = 2 * pb
    elif skill in creature.skill_proficiencies:
        prof = pb
    else:
        prof = 0
    return _mod(creature, SKILL_ABILITY[skill]) + prof


def save_bonus(creature: Creature, ability: Ability) -> int:
    prof = creature.proficiency_bonus if ability in creature.save_proficiencies else 0
    return _mod(creature, ability) + prof


def _result(
    kind: CheckKind, ability: Ability, skill: Skill | None, d20: D20Roll, dc: int
) -> CheckResult:
    if dc < 0:
        raise ValueError("dc must be >= 0")
    success = d20.total >= dc
    if kind is not CheckKind.SAVE and d20.natural == 20:
        success = True
    elif kind is not CheckKind.SAVE and d20.natural == 1:
        success = False
    return CheckResult(
        kind=kind,
        ability=ability,
        skill=skill,
        roll=d20,
        dc=dc,
        success=success,
        margin=d20.total - dc,
    )


def ability_check(
    rng: Rng,
    creature: Creature,
    ability: Ability,
    dc: int,
    *,
    adv: AdvState = AdvState.NORMAL,
    bonus: int = 0,
) -> CheckResult:
    d20 = roll_d20(rng, adv, _mod(creature, ability) + bonus)
    return _result(CheckKind.ABILITY, ability, None, d20, dc)


def skill_check(
    rng: Rng,
    creature: Creature,
    skill: Skill,
    dc: int,
    *,
    adv: AdvState = AdvState.NORMAL,
    bonus: int = 0,
) -> CheckResult:
    d20 = roll_d20(rng, adv, skill_bonus(creature, skill) + bonus)
    return _result(CheckKind.SKILL, SKILL_ABILITY[skill], skill, d20, dc)


def saving_throw(
    rng: Rng,
    creature: Creature,
    ability: Ability,
    dc: int,
    *,
    adv: AdvState = AdvState.NORMAL,
    bonus: int = 0,
) -> CheckResult:
    d20 = roll_d20(rng, adv, save_bonus(creature, ability) + bonus)
    return _result(CheckKind.SAVE, ability, None, d20, dc)


def passive_score(
    creature: Creature, skill: Skill, adv: AdvState = AdvState.NORMAL, bonus: int = 0
) -> int:
    shift = {
        AdvState.NORMAL: 0,
        AdvState.ADVANTAGE: PASSIVE_ADV_SHIFT,
        AdvState.DISADVANTAGE: -PASSIVE_ADV_SHIFT,
    }[adv]
    return PASSIVE_BASE + skill_bonus(creature, skill) + bonus + shift
