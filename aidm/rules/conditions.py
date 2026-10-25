"""THE generic condition interpreter: what a creature's conditions mean for a d20 test or a turn.

Every answer is read from the condition data (data/bg3/conditions.json via
`aidm.data.condition_defs`); there is no per-condition branch here. A creature's effective
conditions are its active instances plus everything they imply (paralyzed -> incapacitated).
An unknown condition key raises `UnknownEntryError` (an engine bug: tools only apply known keys).

Public API:
- `condition_def(name) -> ConditionDef`; `effective_conditions(creature) -> frozenset[str]`.
- `attack_adv_counts(attacker, target, *, melee) -> (adv, dis)`: sources from the attacker's own
  conditions (`own_attacks`) and the target's (`attacks_against_melee/ranged`). Callers add other
  sources (high ground, Help) and combine with `aidm.rules.d20.combine_adv`.
- `attack_adv_names` / `save_adv_names` / `check_adv_names` (M26.2): the same sources as the
  counts, as two lists of condition display names (advantage, disadvantage): the dice show
  says why a roll had advantage.
- `attack_adv(attacker, target, *, melee, adv_sources=0, dis_sources=0) -> AdvState`.
- `melee_hit_auto_crits(target) -> bool`: a melee hit (attacker in the same zone) is a crit.
- `can_attack_target(attacker, target) -> bool`: False when a condition the target applied
  forbids attacking it (charmed).
- `save_auto_fails(creature, ability)`, `save_adv_counts(creature, ability) -> (adv, dis)`,
  `check_adv_counts(creature) -> (adv, dis)` (ability and skill checks).
- `speed_multiplier(creature) -> float` (product of factors; 0 = cannot move).
- `can_take_actions(creature)`, `can_take_reactions(creature)`: False when dead or a condition
  forbids it. `is_incapacitated(creature)`: the "incapacitated" key is effective (breaks
  concentration; surprised forbids actions without incapacitating).
- `condition_resists(creature, damage_type)`, `condition_immune(creature, damage_type)`: damage
  defences granted by conditions (petrified, Protection from Poison); read by the damage choke
  point. `damage_ended_conditions(creature)`: instances that end when the bearer takes damage.
- `condition_ac_bonus(creature) -> int`: AC added by conditions (Shield of Faith);
  `condition_ac_floor(creature) -> int`: the lowest AC conditions allow (Barkskin; 0 = none).
- `effective_speed(creature) -> int`: speed x the condition factor, plus condition speed
  bonuses while the creature can move at all (0 when dead).
- `condition_bonus_dice(creature, *, save=False, check=False) -> tuple[str, ...]`: dice added to
  the bearer's attack rolls, saving throws (`save`) or ability checks (`check`), e.g. Bless
  "1d4"; a leading "-" is a penalty (Bane). `roll_bonus_dice(dice, rng) -> Roll` rolls one of
  them (a penalty has a negative total).
- `condition_riders(attacker_id, target) -> list[(condition, dice, damage type | None)]`: extra
  weapon damage the attacker deals to this target because of conditions it applied (Hunter's
  Mark). `condition_bonus_actions(creature) -> frozenset[str]` (Expeditious Retreat: "dash").
  `condition_blocks_verbal(creature) -> bool` (Silence).
- `attack_consumed_conditions(creature, *, against=False) -> list[ActiveCondition]`: instances
  that end when the bearer makes an attack roll (hidden, helped), or with `against` when an
  attack roll is made against the bearer (guided, M35.3).
- `save_with_conditions(rng, creature, ability, dc, *, adv_sources=0, dis_sources=0, bonus=0)
  -> CheckResult`: the saving throw every effect uses. Condition advantage is combined with the
  caller's sources and condition save dice are rolled (before the d20) into the bonus; an
  auto-failed save still rolls (for the dice tray) but `success` is False. `source_names`
  names the caller's sources (Magic Resistance); unnamed caller sources read "the situation".
  Every result carries `adv_why` (empty for a straight roll).
- `skill_check_with_conditions(rng, creature, skill, dc, *, adv_sources=0, dis_sources=0,
  bonus=0, adv_names=(), dis_names=(), tool=None) -> CheckResult`: the same for a skill check
  (condition check advantage and dice); each of `dis_names` is one more named disadvantage
  source (Darkness, M27.2), each of `adv_names` one more named advantage source (gear boons,
  M27.3); `tool` is the SRD tool the check is made with (`rules.checks.tool_extra`).
- `ability_check_with_conditions(...)`: the same for a plain ability check (DM `request_check`).
"""

from collections.abc import Sequence

from aidm.data.condition_defs import AdvKey, ConditionDef, condition_defs
from aidm.models.abilities import Ability, Skill
from aidm.models.checks import CheckResult
from aidm.models.damage import DamageType
from aidm.models.dice import AdvState, Roll
from aidm.models.state import ActiveCondition, Creature
from aidm.rules.checks import ability_check, saving_throw, skill_check
from aidm.rules.d20 import SITUATION, adv_reasons, combine_adv
from aidm.rules.dice import Rng, roll

INCAPACITATED = "incapacitated"


def condition_def(name: str) -> ConditionDef:
    return condition_defs().get(name)


def effective_conditions(creature: Creature) -> frozenset[str]:
    names: set[str] = set()
    stack = [c.name for c in creature.conditions]
    while stack:
        name = stack.pop()
        if name not in names:
            names.add(name)
            stack.extend(condition_def(name).implies)
    return frozenset(names)


def _defs(creature: Creature) -> list[ConditionDef]:
    return [condition_def(name) for name in sorted(effective_conditions(creature))]


AdvNames = tuple[list[str], list[str]]


def _named(pairs: Sequence[tuple[str, AdvKey | None]]) -> AdvNames:
    adv = [name for name, effect in pairs if effect == "advantage"]
    return adv, [name for name, effect in pairs if effect == "disadvantage"]


def attack_adv_names(attacker: Creature, target: Creature, *, melee: bool) -> AdvNames:
    pairs: list[tuple[str, AdvKey | None]] = [(d.name, d.own_attacks) for d in _defs(attacker)]
    for d in _defs(target):
        pairs.append((d.name, d.attacks_against_melee if melee else d.attacks_against_ranged))
    return _named(pairs)


def attack_adv_counts(attacker: Creature, target: Creature, *, melee: bool) -> tuple[int, int]:
    adv, dis = attack_adv_names(attacker, target, melee=melee)
    return len(adv), len(dis)


def attack_adv(
    attacker: Creature,
    target: Creature,
    *,
    melee: bool,
    adv_sources: int = 0,
    dis_sources: int = 0,
) -> AdvState:
    adv, dis = attack_adv_counts(attacker, target, melee=melee)
    return combine_adv(adv + adv_sources, dis + dis_sources)


def melee_hit_auto_crits(target: Creature) -> bool:
    return any(d.auto_crit_melee for d in _defs(target))


def can_attack_target(attacker: Creature, target: Creature) -> bool:
    return not any(
        c.source_id == target.id and condition_def(c.name).cannot_attack_source
        for c in attacker.conditions
    )


def save_auto_fails(creature: Creature, ability: Ability) -> bool:
    return any(ability.value in d.auto_fail_saves for d in _defs(creature))


def save_adv_names(creature: Creature, ability: Ability) -> AdvNames:
    defs = _defs(creature)
    adv = [d.name for d in defs if ability.value in d.save_advantage]
    return adv, [d.name for d in defs if ability.value in d.save_disadvantage]


def save_adv_counts(creature: Creature, ability: Ability) -> tuple[int, int]:
    adv, dis = save_adv_names(creature, ability)
    return len(adv), len(dis)


def check_adv_names(creature: Creature) -> AdvNames:
    return _named([(d.name, d.own_checks) for d in _defs(creature)])


def check_adv_counts(creature: Creature) -> tuple[int, int]:
    adv, dis = check_adv_names(creature)
    return len(adv), len(dis)


def speed_multiplier(creature: Creature) -> float:
    factor = 1.0
    for d in _defs(creature):
        factor *= d.speed_factor
    return factor


def effective_speed(creature: Creature) -> int:
    factor = speed_multiplier(creature)
    if creature.dead or factor <= 0:
        return 0
    return int(creature.speed * factor) + sum(d.speed_bonus for d in _defs(creature))


def can_take_actions(creature: Creature) -> bool:
    return not creature.dead and all(d.can_act for d in _defs(creature))


def can_take_reactions(creature: Creature) -> bool:
    return not creature.dead and all(d.can_react for d in _defs(creature))


def is_incapacitated(creature: Creature) -> bool:
    return INCAPACITATED in effective_conditions(creature)


def condition_resists(creature: Creature, damage_type: DamageType) -> bool:
    return any(
        d.resist_all_damage or damage_type.value in d.damage_resistances for d in _defs(creature)
    )


def damage_ended_conditions(creature: Creature) -> list[ActiveCondition]:
    return [c for c in creature.conditions if condition_def(c.name).ends_on_damage]


def condition_immune(creature: Creature, damage_type: DamageType) -> bool:
    return any(damage_type.value in d.damage_immunities for d in _defs(creature))


def condition_ac_bonus(creature: Creature) -> int:
    return sum(d.ac_bonus for d in _defs(creature))


def condition_ac_floor(creature: Creature) -> int:
    return max((d.ac_floor or 0 for d in _defs(creature)), default=0)


def condition_bonus_dice(
    creature: Creature, *, save: bool = False, check: bool = False
) -> tuple[str, ...]:
    defs = _defs(creature)
    dice = [d.check_dice if check else d.save_dice if save else d.attack_dice for d in defs]
    return tuple(d for d in dice if d)


def roll_bonus_dice(dice: str, rng: Rng) -> Roll:
    if not dice.startswith("-"):
        return roll(dice, rng)
    rolled = roll(dice[1:], rng)
    return rolled.model_copy(update={"expression": f"-{rolled.expression}", "total": -rolled.total})


def condition_riders(
    attacker_id: str, target: Creature
) -> list[tuple[str, str, DamageType | None]]:
    riders: list[tuple[str, str, DamageType | None]] = []
    for c in target.conditions:
        d = condition_def(c.name)
        if c.source_id == attacker_id and d.source_rider_dice:
            kind = DamageType(d.source_rider_type) if d.source_rider_type else None
            riders.append((c.name, d.source_rider_dice, kind))
    return riders


def condition_bonus_actions(creature: Creature) -> frozenset[str]:
    return frozenset(name for d in _defs(creature) for name in d.bonus_actions)


def condition_blocks_verbal(creature: Creature) -> bool:
    return any(d.blocks_verbal for d in _defs(creature))


def attack_consumed_conditions(
    creature: Creature, *, against: bool = False
) -> list[ActiveCondition]:
    def used(d: ConditionDef) -> bool:
        return d.consumed_by_attack_against if against else d.consumed_by_attack

    return [c for c in creature.conditions if used(condition_def(c.name))]


def _situation(
    rng: Rng,
    creature: Creature,
    own: AdvNames,
    sources: tuple[int, int],
    names: Sequence[str],
    *,
    save: bool,
) -> tuple[AdvState, int, tuple[str, ...]]:
    """Combined advantage, the rolled condition bonus dice and the advantage reasons."""
    caller = list(names) or [SITUATION]
    for_adv = own[0] + (caller if sources[0] else [])
    for_dis = own[1] + (caller if sources[1] else [])
    adv = combine_adv(len(own[0]) + sources[0], len(own[1]) + sources[1])
    dice = condition_bonus_dice(creature, save=save, check=not save)
    extra = sum(roll_bonus_dice(d, rng).total for d in dice)
    return adv, extra, adv_reasons(adv, for_adv, for_dis)


def _with_named(own: AdvNames, adv_names: Sequence[str], dis_names: Sequence[str]) -> AdvNames:
    """Each named situation (Darkness M27.2, a gear boon M27.3) is one more source."""
    return own[0] + list(adv_names), own[1] + list(dis_names)


def save_with_conditions(
    rng: Rng,
    creature: Creature,
    ability: Ability,
    dc: int,
    *,
    adv_sources: int = 0,
    dis_sources: int = 0,
    bonus: int = 0,
    source_names: Sequence[str] = (),
) -> CheckResult:
    own = save_adv_names(creature, ability)
    sources = (adv_sources, dis_sources)
    adv, extra, why = _situation(rng, creature, own, sources, source_names, save=True)
    result = saving_throw(rng, creature, ability, dc, adv=adv, bonus=bonus + extra)
    result = result.model_copy(update={"adv_why": why})
    if save_auto_fails(creature, ability) and result.success:
        return result.model_copy(update={"success": False})
    return result


def skill_check_with_conditions(
    rng: Rng,
    creature: Creature,
    skill: Skill,
    dc: int,
    *,
    adv_sources: int = 0,
    dis_sources: int = 0,
    bonus: int = 0,
    adv_names: Sequence[str] = (),
    dis_names: Sequence[str] = (),
    tool: str | None = None,
) -> CheckResult:
    own = _with_named(check_adv_names(creature), adv_names, dis_names)
    sources = (adv_sources, dis_sources)
    adv, extra, why = _situation(rng, creature, own, sources, (), save=False)
    result = skill_check(rng, creature, skill, dc, adv=adv, bonus=bonus + extra, tool=tool)
    return result.model_copy(update={"adv_why": why})


def ability_check_with_conditions(
    rng: Rng,
    creature: Creature,
    ability: Ability,
    dc: int,
    *,
    adv_sources: int = 0,
    dis_sources: int = 0,
    bonus: int = 0,
    adv_names: Sequence[str] = (),
    dis_names: Sequence[str] = (),
    tool: str | None = None,
) -> CheckResult:
    own = _with_named(check_adv_names(creature), adv_names, dis_names)
    sources = (adv_sources, dis_sources)
    adv, extra, why = _situation(rng, creature, own, sources, (), save=False)
    result = ability_check(rng, creature, ability, dc, adv=adv, bonus=bonus + extra, tool=tool)
    return result.model_copy(update={"adv_why": why})
