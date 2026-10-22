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
- `tool_proficient(creature, tool) -> bool`, `tool_extra(creature, skill, tool) -> int`,
  `tool_and_skill(creature, skill, tool) -> bool` (M27.3, GOAL_ITEMS "proficiency"): a check made
  with an SRD tool (`tool` = its catalogue id) adds the proficiency bonus ONCE when the hero is
  proficient with the tool OR the skill (`tool_extra` is the PROF the skill alone does not give);
  proficient in BOTH -> advantage (house rule; the caller adds the advantage source).
  `ability_check` / `skill_check` take `tool=None`.
- `check_parts(creature, kind, ability, skill, modifier, tool=None) -> tuple[RollPart, ...]`
  (M26.2): the named pieces of a test's modifier: the ability ("DEX"), "PROF" (or
  "EXPERTISE" when doubled; a tool's PROF joins it) and any remainder (Guidance, Bless, Jack
  of All Trades) as one "BONUS"; they sum to `modifier`. Every `CheckResult` built here
  carries them, and `adv_why` = ("the situation",) when the caller passed advantage or
  disadvantage (the condition-aware callers name sources).
- `difficulty_word(tier) -> str`: the tier as a player-facing word ("very hard").
- `passive_score(creature, skill, adv=NORMAL, bonus=0) -> int`: SRD 5.1 "Passive Checks":
  10 + all modifiers that normally apply, +5 with advantage, -5 with disadvantage.

Logging: these functions return results, not events. The caller logs a `CheckResolved` event
with the result (and emits any consequences as their own events).
"""

from aidm.models.abilities import SKILL_ABILITY, Ability, Skill
from aidm.models.checks import CheckKind, CheckResult, DcTier
from aidm.models.dice import AdvState, D20Roll, RollPart
from aidm.models.state import Creature
from aidm.rules.abilities import ability_modifier
from aidm.rules.d20 import SITUATION, roll_d20
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
PROF_PART = "PROF"
EXPERTISE_PART = "EXPERTISE"
BONUS_PART = "BONUS"


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


def tool_proficient(creature: Creature, tool: str | None) -> bool:
    return tool is not None and creature.pc is not None and tool in creature.pc.tool_proficiencies


def _skilled(creature: Creature, skill: Skill | None) -> bool:
    return skill is not None and (
        skill in creature.skill_proficiencies or skill in creature.skill_expertise
    )


def tool_extra(creature: Creature, skill: Skill | None, tool: str | None) -> int:
    if not tool_proficient(creature, tool) or _skilled(creature, skill):
        return 0
    return creature.proficiency_bonus


def tool_and_skill(creature: Creature, skill: Skill | None, tool: str | None) -> bool:
    return tool_proficient(creature, tool) and _skilled(creature, skill)


def difficulty_word(tier: DcTier) -> str:
    return tier.value.replace("_", " ")


def check_parts(
    creature: Creature,
    kind: CheckKind,
    ability: Ability,
    skill: Skill | None,
    modifier: int,
    tool: str | None = None,
) -> tuple[RollPart, ...]:
    mod = _mod(creature, ability)
    prof, prof_name = 0, PROF_PART
    if kind is CheckKind.SKILL and skill is not None:
        prof = skill_bonus(creature, skill) - mod
        prof_name = EXPERTISE_PART if skill in creature.skill_expertise else PROF_PART
    elif kind is CheckKind.SAVE:
        prof = save_bonus(creature, ability) - mod
    if kind is not CheckKind.SAVE:
        prof += tool_extra(creature, skill, tool)
    parts = [RollPart(name=ability.value.upper(), value=mod)]
    if prof:
        parts.append(RollPart(name=prof_name, value=prof))
    if modifier - mod - prof:
        parts.append(RollPart(name=BONUS_PART, value=modifier - mod - prof))
    return tuple(parts)


def _result(
    creature: Creature,
    kind: CheckKind,
    ability: Ability,
    skill: Skill | None,
    d20: D20Roll,
    dc: int,
    tool: str | None = None,
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
        parts=check_parts(creature, kind, ability, skill, d20.modifier, tool),
        adv_why=() if d20.adv is AdvState.NORMAL else (SITUATION,),
    )


def ability_check(
    rng: Rng,
    creature: Creature,
    ability: Ability,
    dc: int,
    *,
    adv: AdvState = AdvState.NORMAL,
    bonus: int = 0,
    tool: str | None = None,
) -> CheckResult:
    d20 = roll_d20(rng, adv, _mod(creature, ability) + tool_extra(creature, None, tool) + bonus)
    return _result(creature, CheckKind.ABILITY, ability, None, d20, dc, tool)


def skill_check(
    rng: Rng,
    creature: Creature,
    skill: Skill,
    dc: int,
    *,
    adv: AdvState = AdvState.NORMAL,
    bonus: int = 0,
    tool: str | None = None,
) -> CheckResult:
    d20 = roll_d20(
        rng, adv, skill_bonus(creature, skill) + tool_extra(creature, skill, tool) + bonus
    )
    return _result(creature, CheckKind.SKILL, SKILL_ABILITY[skill], skill, d20, dc, tool)


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
    return _result(creature, CheckKind.SAVE, ability, None, d20, dc)


def passive_score(
    creature: Creature, skill: Skill, adv: AdvState = AdvState.NORMAL, bonus: int = 0
) -> int:
    shift = {
        AdvState.NORMAL: 0,
        AdvState.ADVANTAGE: PASSIVE_ADV_SHIFT,
        AdvState.DISADVANTAGE: -PASSIVE_ADV_SHIFT,
    }[adv]
    return PASSIVE_BASE + skill_bonus(creature, skill) + bonus + shift
