"""THE feature hook interpreter: combat-time queries over data/bg3/features.json (SPEC 7.4).

Features are data (`aidm.data.feature_defs`); this module is the one place that reads their
hooks for attacks, damage, AC, saves and actions. Build-time effects (resources, resistances, HP,
proficiencies, expertise, spell grants) live in `aidm.rules.feature_build`. The feature registry
arrives as an argument (`feats`); nothing here loads files and nothing branches on a feature id.

A creature's features are `pc.features` + `pc.traits` (class/subclass features, picked options
and race traits), active from each hook's `min_level` at the character level (`pc.level`; 1 for
creatures without `pc`). A `toggle` hook's `while_active` hooks join while the creature carries
the toggle's condition with `source_id == key`.

Public API:
- `character_level(creature) -> int`; `creature_feature_ids(creature) -> list[str]`.
- `feature_hooks(ids, level, feats) -> list[tuple[str, FeatureHook]]`: (feature id, hook) pairs
  active at `level`; `creature_hooks(creature, feats)` adds active toggle effects;
  `toggle_is_on(creature, hook) -> bool`.
- `dice_at_level(dice_by_level, level) -> str | None`: the entry with the highest level <= level.
- `attack_bonus_mods(creature, feats, ctx) -> int`: fighting-style attack bonuses (Archery).
- `damage_bonus_mods(creature, feats, ctx) -> int`: flat damage bonuses (Dueling).
- `damage_riders(creature, feats, ctx) -> list[DamageRider]`: riders whose weapon filter and
  trigger match and whose once-per-turn use is not spent (Sneak Attack, Colossus Slayer).
- `damage_reroll_below(creature, feats, ctx) -> int`: reroll damage dice under this value
  (Great Weapon Fighting), 0 = none. `offhand_adds_ability(creature, feats, ctx) -> bool`.
- `feature_ac_bonus(creature, feats, *, armored) -> int` (Defense).
- `save_advantage_sources(creature, feats, ability, tags) -> list[str]`: feature ids giving
  advantage on this save against an effect carrying any of `tags` (condition keys, damage types,
  "magic").
- `crit_threshold(creature, feats) -> int` (20, or Improved Critical's 19).
- `attacks_per_action(creature, feats) -> int` (1 + the best Extra Attack).
- `feature_actions(creature, feats) -> list[FeatureAction]`: bonus actions and extra actions.
- `rerolls_natural_ones(creature, feats, test) -> bool` ("attack", "check", "save").
- `healing_bonus(creature, feats, spell_level) -> int`; `kill_temp_hp(creature, feats) -> int`.
- `toggle_feature(creature, feats, key, *, on) -> list[AnyEvent]`: switch a rage-style toggle:
  on = spend its resource (ResourceError when spent) and apply its condition (source id = key);
  off = remove that condition; no events when it is already in the requested state.
  `FeatureUseError(ValueError)`: the creature has no toggle `key`.
"""

from collections.abc import Collection, Sequence

from aidm.data.feature_defs import FeatureDef
from aidm.data.feature_hooks import (
    AdvantageOnHook,
    BonusActionHook,
    DamageRiderHook,
    ExtraActionHook,
    ExtraAttackHook,
    FeatureHook,
    FightingStyleHook,
    HealingBonusHook,
    ImprovedCriticalHook,
    KillTempHpHook,
    RerollOnesHook,
    SneakAttackHook,
    ToggleHook,
    WeaponNeed,
)
from aidm.data.registry import Registry
from aidm.models.abilities import Ability
from aidm.models.damage import DamageType
from aidm.models.dice import AdvState
from aidm.models.events import AnyEvent
from aidm.models.features import ActionEconomy, AttackContext, DamageRider, FeatureAction
from aidm.models.state import Creature
from aidm.rules.abilities import ability_modifier
from aidm.rules.condition_timing import apply_condition, new_condition, remove_condition
from aidm.rules.resources import resource_left, spend_resource

DEFAULT_CRIT_ON = 20
LEVEL_PLACEHOLDER = "LEVEL"

type HookPair = tuple[str, FeatureHook]


def character_level(creature: Creature) -> int:
    return creature.pc.level if creature.pc is not None else 1


def creature_feature_ids(creature: Creature) -> list[str]:
    if creature.pc is None:
        return []
    return list(dict.fromkeys([*creature.pc.features, *creature.pc.traits]))


def feature_hooks(ids: Sequence[str], level: int, feats: Registry[FeatureDef]) -> list[HookPair]:
    pairs: list[HookPair] = []
    for feature_id in dict.fromkeys(ids):
        for hook in feats.get(feature_id).hooks:
            if hook.min_level <= level:
                pairs.append((feature_id, hook))
    return pairs


def toggle_is_on(creature: Creature, hook: ToggleHook) -> bool:
    return any(c.name == hook.condition and c.source_id == hook.key for c in creature.conditions)


def creature_hooks(creature: Creature, feats: Registry[FeatureDef]) -> list[HookPair]:
    level = character_level(creature)
    pairs = feature_hooks(creature_feature_ids(creature), level, feats)
    extra: list[HookPair] = []
    for feature_id, hook in pairs:
        if isinstance(hook, ToggleHook) and toggle_is_on(creature, hook):
            extra.extend((feature_id, h) for h in hook.while_active if h.min_level <= level)
    return pairs + extra


def dice_at_level(dice_by_level: dict[int, str], level: int) -> str | None:
    eligible = [lvl for lvl in dice_by_level if lvl <= level]
    return dice_by_level[max(eligible)] if eligible else None


def _weapon_ok(need: WeaponNeed, ctx: AttackContext) -> bool:
    match need:
        case "any":
            return True
        case "melee":
            return not ctx.ranged
        case "ranged":
            return ctx.ranged
        case "finesse_or_ranged":
            return ctx.finesse or ctx.ranged
        case "melee_one_handed":
            return not ctx.ranged and not ctx.two_handed and not ctx.other_hand_weapon
        case "melee_two_handed":
            return not ctx.ranged and ctx.two_handed
        case "offhand":
            return ctx.offhand


def _styles(creature: Creature, feats: Registry[FeatureDef]) -> list[FightingStyleHook]:
    return [h for _, h in creature_hooks(creature, feats) if isinstance(h, FightingStyleHook)]


def attack_bonus_mods(creature: Creature, feats: Registry[FeatureDef], ctx: AttackContext) -> int:
    return sum(h.attack_bonus for h in _styles(creature, feats) if _weapon_ok(h.weapon, ctx))


def damage_bonus_mods(creature: Creature, feats: Registry[FeatureDef], ctx: AttackContext) -> int:
    return sum(h.damage_bonus for h in _styles(creature, feats) if _weapon_ok(h.weapon, ctx))


def damage_reroll_below(creature: Creature, feats: Registry[FeatureDef], ctx: AttackContext) -> int:
    values = [h.reroll_damage_below for h in _styles(creature, feats) if _weapon_ok(h.weapon, ctx)]
    return max(values, default=0)


def offhand_adds_ability(
    creature: Creature, feats: Registry[FeatureDef], ctx: AttackContext
) -> bool:
    return ctx.offhand and any(h.offhand_ability_damage for h in _styles(creature, feats))


def feature_ac_bonus(creature: Creature, feats: Registry[FeatureDef], *, armored: bool) -> int:
    return sum(h.ac_bonus for h in _styles(creature, feats) if armored or not h.requires_armor)


def _as_rider(hook: SneakAttackHook) -> DamageRiderHook:
    return DamageRiderHook(
        min_level=hook.min_level,
        dice_by_level=hook.dice_by_level,
        weapon="finesse_or_ranged",
        trigger="advantage_or_ally",
        once_per_turn=True,
    )


def _triggered(hook: DamageRiderHook, ctx: AttackContext) -> bool:
    match hook.trigger:
        case "always":
            return True
        case "advantage_or_ally":
            return ctx.adv is AdvState.ADVANTAGE or (
                ctx.ally_adjacent and ctx.adv is not AdvState.DISADVANTAGE
            )
        case "target_wounded":
            return ctx.target_wounded
        case "crit":
            return ctx.crit


def _rider(feature_id: str, hook: DamageRiderHook, level: int, ctx: AttackContext) -> DamageRider:
    dice = dice_at_level(hook.dice_by_level, level)
    if hook.weapon_dice and ctx.weapon_die:
        weapon = f"{hook.weapon_dice}d{ctx.weapon_die}"
        dice = weapon if dice is None else f"{dice}+{weapon}"
    return DamageRider(
        feature=feature_id,
        dice=dice,
        flat=hook.flat,
        damage_type=DamageType(hook.damage_type) if hook.damage_type else None,
        once_per_turn=hook.once_per_turn,
        doubles_on_crit=hook.trigger != "crit",
    )


def damage_riders(
    creature: Creature, feats: Registry[FeatureDef], ctx: AttackContext
) -> list[DamageRider]:
    level = character_level(creature)
    riders: list[DamageRider] = []
    for feature_id, raw in creature_hooks(creature, feats):
        hook = _as_rider(raw) if isinstance(raw, SneakAttackHook) else raw
        if not isinstance(hook, DamageRiderHook):
            continue
        if hook.once_per_turn and feature_id in ctx.used_once_per_turn:
            continue
        if _weapon_ok(hook.weapon, ctx) and _triggered(hook, ctx):
            rider = _rider(feature_id, hook, level, ctx)
            if rider.dice is not None or rider.flat:
                riders.append(rider)
    return riders


def save_advantage_sources(
    creature: Creature, feats: Registry[FeatureDef], ability: Ability, tags: Collection[str]
) -> list[str]:
    sources: list[str] = []
    for feature_id, hook in creature_hooks(creature, feats):
        if not isinstance(hook, AdvantageOnHook):
            continue
        if hook.abilities and ability.value not in hook.abilities:
            continue
        if any(tag in tags for tag in hook.saves_against):
            sources.append(feature_id)
    return list(dict.fromkeys(sources))


def crit_threshold(creature: Creature, feats: Registry[FeatureDef]) -> int:
    values = [
        h.crit_on for _, h in creature_hooks(creature, feats) if isinstance(h, ImprovedCriticalHook)
    ]
    return min([DEFAULT_CRIT_ON, *values])


def attacks_per_action(creature: Creature, feats: Registry[FeatureDef]) -> int:
    extra = [
        h.attacks for _, h in creature_hooks(creature, feats) if isinstance(h, ExtraAttackHook)
    ]
    return 1 + max(extra, default=0)


def _available(creature: Creature, resource: str | None) -> bool:
    return resource is None or resource_left(creature, resource) > 0


def feature_actions(creature: Creature, feats: Registry[FeatureDef]) -> list[FeatureAction]:
    level = str(character_level(creature))
    options: list[FeatureAction] = []
    for feature_id, hook in creature_hooks(creature, feats):
        if isinstance(hook, BonusActionHook):
            heal = hook.heal.replace(LEVEL_PLACEHOLDER, level) if hook.heal else None
            options.extend(
                FeatureAction(
                    feature=feature_id,
                    action=action,
                    economy=ActionEconomy.BONUS_ACTION,
                    resource=hook.resource,
                    available=_available(creature, hook.resource),
                    heal=heal,
                )
                for action in hook.actions
            )
        elif isinstance(hook, ExtraActionHook):
            options.append(
                FeatureAction(
                    feature=feature_id,
                    action="extra_action",
                    economy=ActionEconomy.EXTRA_ACTION,
                    resource=hook.resource,
                    available=_available(creature, hook.resource),
                )
            )
    return options


def rerolls_natural_ones(creature: Creature, feats: Registry[FeatureDef], test: str) -> bool:
    hooks = creature_hooks(creature, feats)
    return any(isinstance(h, RerollOnesHook) and test in h.tests for _, h in hooks)


def healing_bonus(creature: Creature, feats: Registry[FeatureDef], spell_level: int) -> int:
    total = 0
    for _, hook in creature_hooks(creature, feats):
        if isinstance(hook, HealingBonusHook) and spell_level >= hook.min_spell_level:
            total += hook.base + hook.per_spell_level * spell_level
    return total


def kill_temp_hp(creature: Creature, feats: Registry[FeatureDef]) -> int:
    best = 0
    for _, hook in creature_hooks(creature, feats):
        if isinstance(hook, KillTempHpHook):
            amount = ability_modifier(creature.abilities[Ability(hook.ability)])
            amount += character_level(creature) if hook.add_level else 0
            best = max(best, amount, hook.minimum)
    return best


class FeatureUseError(ValueError):
    """The creature has no such feature option (an engine or tool-layer bug)."""


def toggle_feature(
    creature: Creature, feats: Registry[FeatureDef], key: str, *, on: bool
) -> list[AnyEvent]:
    hooks = feature_hooks(creature_feature_ids(creature), character_level(creature), feats)
    toggle = next((h for _, h in hooks if isinstance(h, ToggleHook) and h.key == key), None)
    if toggle is None:
        raise FeatureUseError(f"{creature.id!r} has no toggle {key!r}")
    if on == toggle_is_on(creature, toggle):
        return []
    if not on:
        return remove_condition(creature, toggle.condition, toggle.key)
    events = spend_resource(creature, toggle.resource) if toggle.resource else []
    return events + apply_condition(creature, new_condition(toggle.condition, source_id=toggle.key))
