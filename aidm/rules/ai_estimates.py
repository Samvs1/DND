"""Expected-value estimates for the combat AI (M3.10, SPEC 7.4 Monster AI).

The AI scores options by expected outcomes computed from the SAME inputs the resolution uses:
`rules.hit_chance` for attack rolls (advantage, cover, high ground, crits), `rules.damage.
damage_after_defenses` for resistances, `rules.checks.save_bonus` plus the condition save
modifiers for saving throws. Nothing here rolls dice or changes state.

Public API:
- `dice_average(dice, factor=1) -> float`: the mean of a plain dice expression ("" = 0); `factor`
  multiplies the dice count (cantrip scaling). `crit_extra(dice) -> float`: the mean of its dice
  part only (what a critical hit adds).
- `defense_factor(creature, damage_type) -> float`: 0 immune, 0.5 resistant, 2 vulnerable.
- `save_fail_chance(creature, ability, dc) -> float`: d20 + save bonus < DC, with auto-fails and
  condition advantage/disadvantage.
- `attack_expectation(state, attacker_id, target_id, profile, feats) -> float`: the expected
  damage of one attack (hit and crit chance, extra damage parts, defences; 0 out of range).
- `condition_harm(name) -> float` / `condition_benefit(name) -> float`: how much a condition
  hinders (1 = cannot act) or helps its bearer, read from its data entry.
- `SpellNumbers(save_dc, attack_bonus, modifier, char_level, range_feet)`: a caster's numbers.
- `EffectEstimate(damage, heal, control, buff)`; `effects_estimate(state, caster_id, target_id,
  effects, numbers) -> EffectEstimate`: the DSL effects on one target instance (damage after
  defences, healing, expected disabling weight, buff weight).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from aidm.data.feature_defs import FeatureDef
from aidm.data.registry import Registry
from aidm.data.spell_defs import (
    AcBuffEffect,
    ApplyConditionEffect,
    AttackRollEffect,
    DamageEffect,
    Effect,
    HealEffect,
    HpPoolEffect,
    SaveEffect,
    TempHpEffect,
)
from aidm.models.abilities import Ability
from aidm.models.combat import AttackProfile
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.state import Creature, GameState
from aidm.rules.checks import save_bonus
from aidm.rules.conditions import condition_def, save_adv_counts, save_auto_fails
from aidm.rules.damage import damage_after_defenses
from aidm.rules.dice import parse_dice
from aidm.rules.hit_chance import hit_chance
from aidm.rules.spell_context import CANTRIP_TIERS

_PROBE = 100
_DISABLED = 1.0


def dice_average(dice: str, factor: int = 1) -> float:
    if not dice:
        return 0.0
    expr = parse_dice(dice)
    mean = sum(t.count * (t.sides + 1) / 2 for t in expr.terms) * factor
    return mean + expr.modifier


def crit_extra(dice: str) -> float:
    if not dice:
        return 0.0
    expr = parse_dice(dice)
    return sum(t.count * (t.sides + 1) / 2 for t in expr.terms)


def defense_factor(creature: Creature, damage_type: DamageType) -> float:
    packet = DamagePacket(amount=_PROBE, damage_type=damage_type)
    return damage_after_defenses(creature, packet) / _PROBE


def save_fail_chance(creature: Creature, ability: Ability, dc: int) -> float:
    if save_auto_fails(creature, ability):
        return 1.0
    need = dc - save_bonus(creature, ability)
    success = min(1.0, max(0.0, (21 - need) / 20))
    adv, dis = save_adv_counts(creature, ability)
    if adv and not dis:
        success = 1 - (1 - success) ** 2
    elif dis and not adv:
        success = success**2
    return 1.0 - success


def attack_expectation(
    state: GameState,
    attacker_id: str,
    target_id: str,
    profile: AttackProfile,
    feats: Registry[FeatureDef],
) -> float:
    chance = hit_chance(state, attacker_id, target_id, profile, feats)
    if chance.probability <= 0:
        return 0.0
    target = state.creatures[target_id]
    parts = [(profile.damage, profile.damage_type)]
    parts.extend((x.dice, x.damage_type) for x in profile.extra_damage)
    hit = sum(dice_average(d) * defense_factor(target, t) for d, t in parts if d)
    crit = sum(crit_extra(d) * defense_factor(target, t) for d, t in parts if d)
    return max(0.0, chance.probability * hit + chance.crit_chance * crit)


def _closure(name: str) -> list[str]:
    seen: list[str] = []
    stack = [name]
    while stack:
        key = stack.pop()
        if key not in seen:
            seen.append(key)
            stack.extend(condition_def(key).implies)
    return seen


def condition_harm(name: str) -> float:
    harm = 0.0
    for key in _closure(name):
        cd = condition_def(key)
        if not cd.can_act:
            return _DISABLED
        if cd.speed_factor == 0:
            harm += 0.4
        if cd.own_attacks == "disadvantage" or (cd.attack_dice or "").startswith("-"):
            harm += 0.3
        if "advantage" in (cd.attacks_against_melee, cd.attacks_against_ranged):
            harm += 0.3
        harm += 0.1 * len(cd.save_disadvantage) + (0.1 if cd.speed_factor < 1 else 0.0)
    return min(harm, 0.9)


def condition_benefit(name: str) -> float:
    cd = condition_def(name)
    gain = 0.3 if cd.attack_dice and not cd.attack_dice.startswith("-") else 0.0
    gain += 0.3 if cd.ac_bonus > 0 or cd.ac_floor else 0.0
    gain += 0.2 if cd.save_dice and not cd.save_dice.startswith("-") else 0.0
    gain += 0.3 if cd.damage_resistances or cd.resist_all_damage else 0.0
    gain += 0.3 if cd.own_attacks == "advantage" else 0.0
    gain += 0.3 if cd.source_rider_dice else 0.0
    return gain


@dataclass(frozen=True)
class SpellNumbers:
    save_dc: int
    attack_bonus: int
    modifier: int
    char_level: int
    range_feet: int = 5


@dataclass(frozen=True)
class EffectEstimate:
    damage: float = 0.0
    heal: float = 0.0
    control: float = 0.0
    buff: float = 0.0

    def __add__(self, other: "EffectEstimate") -> "EffectEstimate":
        return EffectEstimate(
            self.damage + other.damage,
            self.heal + other.heal,
            self.control + other.control,
            self.buff + other.buff,
        )


@dataclass(frozen=True)
class _Ctx:
    state: GameState
    caster_id: str
    target: Creature
    numbers: SpellNumbers
    feats: Registry[FeatureDef]


def _spell_hit(ctx: _Ctx, effect: AttackRollEffect) -> float:
    profile = AttackProfile(
        key="spell",
        name="spell",
        attack_bonus=ctx.numbers.attack_bonus,
        ranged=effect.attack == "ranged",
        range_normal=max(5, ctx.numbers.range_feet),
    )
    chance = hit_chance(ctx.state, ctx.caster_id, ctx.target.id, profile, ctx.feats)
    return chance.probability


def _save(ctx: _Ctx, effect: SaveEffect, scale: float) -> EffectEstimate:
    fail = save_fail_chance(ctx.target, Ability(effect.ability), ctx.numbers.save_dc)
    total = _walk(ctx, effect.on_fail, scale * fail)
    if effect.on_success == "half":
        halved = _walk(ctx, effect.on_fail, scale * (1 - fail) * 0.5)
        total = total + EffectEstimate(damage=halved.damage)
    elif isinstance(effect.on_success, tuple):
        total = total + _walk(ctx, effect.on_success, scale * (1 - fail))
    return total


def _amount(ctx: _Ctx, dice: str, add_modifier: bool, scaling: bool = False) -> float:
    factor = 1 + sum(ctx.numbers.char_level >= t for t in CANTRIP_TIERS) if scaling else 1
    return dice_average(dice, factor) + (ctx.numbers.modifier if add_modifier else 0)


def _one(ctx: _Ctx, effect: Effect, scale: float) -> EffectEstimate:
    match effect:
        case AttackRollEffect():
            return _walk(ctx, effect.on_hit, scale * _spell_hit(ctx, effect))
        case SaveEffect():
            return _save(ctx, effect, scale)
        case DamageEffect():
            mean = _amount(ctx, effect.dice, effect.add_modifier, effect.cantrip_scaling)
            factor = defense_factor(ctx.target, DamageType(effect.damage_type))
            return EffectEstimate(damage=scale * max(0.0, mean) * factor)
        case HealEffect():
            return EffectEstimate(heal=scale * _amount(ctx, effect.dice, effect.add_modifier))
        case TempHpEffect():
            return EffectEstimate(buff=scale * 0.1 * _amount(ctx, effect.dice, effect.add_modifier))
        case ApplyConditionEffect():
            harm, gain = condition_harm(effect.condition), condition_benefit(effect.condition)
            return EffectEstimate(control=scale * harm, buff=scale * gain)
        case AcBuffEffect():
            return EffectEstimate(buff=scale * 0.3)
        case HpPoolEffect():
            asleep = ctx.target.hp <= dice_average(effect.dice)
            return EffectEstimate(control=scale * _DISABLED if asleep else 0.0)
        case _:
            return EffectEstimate()


def _walk(ctx: _Ctx, effects: Sequence[Effect], scale: float) -> EffectEstimate:
    total = EffectEstimate()
    for effect in effects:
        total = total + _one(ctx, effect, scale)
    return total


def effects_estimate(
    state: GameState,
    caster_id: str,
    target_id: str,
    effects: Sequence[Effect],
    numbers: SpellNumbers,
    feats: Registry[FeatureDef],
) -> EffectEstimate:
    ctx = _Ctx(state, caster_id, state.creatures[target_id], numbers, feats)
    return _walk(ctx, effects, 1.0)
