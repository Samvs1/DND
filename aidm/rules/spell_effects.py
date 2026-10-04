"""THE spell effect interpreter: runs a `SpellDef`'s effect list on one target instance.

`aidm.rules.spells.cast_spell` validates the cast, builds one `CastContext` and calls
`run_effects` per target instance. Every effect kind is handled here generically; there is no
per-spell code. The context keeps a projected state (`rules.projection`) so later effects see
earlier ones (a second beam at a creature the first one dropped).

Semantics (SRD 5.1 unless noted):
- attack_roll: THE attack path (`rules.attacks.roll_attack`) with a spell `AttackProfile`
  (spell attack bonus, range band); a crit doubles the on-hit damage dice.
- save: `save_with_conditions` against the caster's spell DC (Bless dice, condition and feature
  advantage, e.g. gnome cunning against "magic"), logged as `CheckResolved`; "half" halves the
  on-fail damage (rounded down) and skips its other effects.
- damage: dice (cantrip tiers at character levels 5/11/17, `upcast_dice` per slot level above)
  through `rules.attacks.deal_damage` (resistances, concentration checks, kill temp HP).
  Area spells roll each damage/heal effect once for every target (`shared`).
- heal: dice + spellcasting modifier + feature healing bonus (Disciple of Life uses the cast
  level); temp_hp never stacks (only a higher value replaces).
- apply_condition / ac_buff: the caster is the source; rounds tick at the end of the caster's
  turns; `save_ends` repeats the save against the spell DC at the end of the bearer's turns; on
  a concentration spell the applied condition is linked to the concentration. A target that
  becomes incapacitated loses its own concentration.
- surface: one `ZoneSurfaceAdded` per zone and surface for the cast.
- multi_target: the sub-effects run on every other creature of the current target's zone (or
  zone and neighbours), sharing rolls.

Public API: `CastContext`, `cast_dice(effect_dice, ctx, *, cantrip_scaling, upcast_dice,
add_modifier) -> str`, `spell_attack_profile(spell, name, ctx) -> AttackProfile`,
`run_effects(ctx, effects, target_id, *, crit=False, half=False, shared=False) -> None`,
`place_surface(ctx, effect, zone_id) -> None`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from aidm.data.feature_defs import FeatureDef
from aidm.data.registry import Registry
from aidm.data.spell_defs import (
    AcBuffEffect,
    ApplyConditionEffect,
    AttackRollEffect,
    DamageEffect,
    Effect,
    HealEffect,
    MultiTargetEffect,
    RemoveConditionEffect,
    SaveEffect,
    SpellDef,
    SurfaceEffect,
    TempHpEffect,
)
from aidm.models.abilities import Ability
from aidm.models.combat import AttackEconomy, AttackProfile
from aidm.models.combat_events import ZoneSurfaceAdded
from aidm.models.conditions import ConditionLink, SaveEnds
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.dice import Roll
from aidm.models.events import AnyEvent, CheckResolved, DiceRolled, TempHpSet
from aidm.models.state import GameState
from aidm.models.zones import ZoneSurface
from aidm.rules.attacks import deal_damage, roll_attack
from aidm.rules.concentration import concentration_upkeep
from aidm.rules.condition_timing import apply_condition, new_condition, remove_condition
from aidm.rules.conditions import save_with_conditions
from aidm.rules.damage import resolve_healing
from aidm.rules.dice import Rng, parse_dice, roll
from aidm.rules.features import healing_bonus, save_advantage_sources
from aidm.rules.projection import project_state
from aidm.rules.spell_targets import CasterNumbers, area_creatures, spell_band

CANTRIP_TIERS = (5, 11, 17)
MAGIC_TAG = "magic"


@dataclass
class CastContext:
    rng: Rng
    spell: SpellDef
    caster_id: str
    cast_level: int
    numbers: CasterNumbers
    char_level: int
    feats: Registry[FeatureDef]
    state: GameState
    name: str = ""
    events: list[AnyEvent] = field(default_factory=list[AnyEvent])
    links: list[ConditionLink] = field(default_factory=list[ConditionLink])
    rolls: dict[int, Roll] = field(default_factory=dict[int, Roll])
    surfaces: set[tuple[str, str]] = field(default_factory=set[tuple[str, str]])

    def emit(self, events: Sequence[AnyEvent]) -> None:
        if events:
            self.events.extend(events)
            self.state = project_state(self.state, events)


def _scaled(dice: str, factor: int) -> str:
    expr = parse_dice(dice)
    parts = [f"{t.count * factor}d{t.sides}" for t in expr.terms]
    if expr.modifier or not parts:
        parts.append(str(expr.modifier))
    return "+".join(parts).replace("+-", "-")


def cast_dice(
    effect_dice: str,
    ctx: CastContext,
    *,
    cantrip_scaling: bool = False,
    upcast_dice: str | None = None,
    add_modifier: bool = False,
) -> str:
    dice = effect_dice
    if cantrip_scaling:
        dice = _scaled(dice, 1 + sum(ctx.char_level >= tier for tier in CANTRIP_TIERS))
    extra = max(0, ctx.cast_level - ctx.spell.level)
    if upcast_dice and extra:
        dice = "+".join([dice, *([upcast_dice] * extra)])
    if add_modifier and ctx.numbers.modifier:
        dice = f"{dice}+{ctx.numbers.modifier}".replace("+-", "-")
    return str(parse_dice(dice))


def spell_attack_profile(spell: SpellDef, name: str, ctx: CastContext) -> AttackProfile:
    band = spell_band(spell)
    ranged = spell.range.kind == "feet" and band.normal_hops > 0
    return AttackProfile(
        key=spell.index,
        name=name,
        attack_bonus=ctx.numbers.attack_bonus,
        ranged=ranged,
        range_normal=spell.range.feet or 5,
        economy=AttackEconomy.ACTION,
    )


def _roll(ctx: CastContext, effect: Effect, dice: str, *, crit: bool, shared: bool) -> Roll:
    key = id(effect)
    if shared and key in ctx.rolls:
        return ctx.rolls[key]
    rolled = roll(dice, ctx.rng, crit=crit)
    ctx.emit([DiceRolled(roll=rolled, roller_id=ctx.caster_id, label=ctx.name or ctx.spell.index)])
    if shared:
        ctx.rolls[key] = rolled
    return rolled


def _damage(
    ctx: CastContext, effect: DamageEffect, target_id: str, crit: bool, half: bool, shared: bool
) -> None:
    dice = cast_dice(
        effect.dice,
        ctx,
        cantrip_scaling=effect.cantrip_scaling,
        upcast_dice=effect.upcast_dice,
        add_modifier=effect.add_modifier,
    )
    total = _roll(ctx, effect, dice, crit=crit, shared=shared).total
    amount = max(0, total) // 2 if half else total
    packet = DamagePacket(amount=amount, damage_type=DamageType(effect.damage_type))
    ctx.emit(
        deal_damage(
            ctx.rng, ctx.state, ctx.caster_id, target_id, [packet], crit=crit, feats=ctx.feats
        )
    )


def _heal(
    ctx: CastContext, effect: HealEffect | TempHpEffect, target_id: str, shared: bool
) -> None:
    dice = cast_dice(
        effect.dice, ctx, upcast_dice=effect.upcast_dice, add_modifier=effect.add_modifier
    )
    amount = _roll(ctx, effect, dice, crit=False, shared=shared).total
    target = ctx.state.creatures[target_id]
    if isinstance(effect, TempHpEffect):
        if amount > target.temp_hp and not target.dead:
            ctx.emit([TempHpSet(creature_id=target_id, temp_hp=amount)])
        return
    caster = ctx.state.creatures[ctx.caster_id]
    amount += healing_bonus(caster, ctx.feats, ctx.cast_level)
    ctx.emit(resolve_healing(target, max(0, amount)))


def _condition(
    ctx: CastContext, effect: ApplyConditionEffect | AcBuffEffect, target_id: str
) -> None:
    rounds = effect.rounds or ctx.spell.duration_rounds
    save_ends = None
    if isinstance(effect, ApplyConditionEffect) and effect.save_ends:
        save_ends = SaveEnds(ability=Ability(effect.save_ends), dc=ctx.numbers.save_dc)
    condition = new_condition(
        effect.condition,
        source_id=ctx.caster_id,
        rounds=rounds,
        tick_creature_id=ctx.caster_id if rounds else None,
        save_ends=save_ends,
    )
    applied = apply_condition(ctx.state.creatures[target_id], condition)
    ctx.emit(applied)
    if applied and ctx.spell.concentration:
        ctx.links.append(ConditionLink(creature_id=target_id, name=effect.condition))
    if target_id != ctx.caster_id:
        ctx.emit(concentration_upkeep(ctx.state, target_id))


def _save_tags(effects: Sequence[Effect]) -> set[str]:
    tags = {MAGIC_TAG}
    for effect in effects:
        if isinstance(effect, (ApplyConditionEffect, AcBuffEffect)):
            tags.add(effect.condition)
        elif isinstance(effect, DamageEffect):
            tags.add(effect.damage_type)
    return tags


def _save(ctx: CastContext, effect: SaveEffect, target_id: str, shared: bool) -> None:
    target = ctx.state.creatures[target_id]
    if target.dead:
        return
    ability = Ability(effect.ability)
    sources = save_advantage_sources(target, ctx.feats, ability, _save_tags(effect.on_fail))
    result = save_with_conditions(
        ctx.rng, target, ability, ctx.numbers.save_dc, adv_sources=min(1, len(sources))
    )
    reason = f"{ctx.spell.index} save"
    ctx.emit([CheckResolved(creature_id=target_id, result=result, reason=reason)])
    if not result.success:
        run_effects(ctx, effect.on_fail, target_id, shared=shared)
    elif effect.on_success == "half":
        run_effects(ctx, effect.on_fail, target_id, half=True, shared=shared)
    elif not isinstance(effect.on_success, str):
        run_effects(ctx, effect.on_success, target_id, shared=shared)


def _attack(ctx: CastContext, effect: AttackRollEffect, target_id: str, shared: bool) -> None:
    profile = spell_attack_profile(ctx.spell, ctx.name or ctx.spell.index, ctx)
    if effect.attack == "melee":
        profile = profile.model_copy(update={"ranged": False, "range_normal": 5})
    rolled = roll_attack(ctx.rng, ctx.state, ctx.caster_id, target_id, profile, ctx.feats)
    ctx.emit(rolled.events)
    if rolled.hit:
        run_effects(ctx, effect.on_hit, target_id, crit=rolled.crit, shared=shared)


def place_surface(ctx: CastContext, effect: SurfaceEffect, zone_id: str) -> None:
    if (zone_id, effect.surface) in ctx.surfaces:
        return
    ctx.surfaces.add((zone_id, effect.surface))
    surface = ZoneSurface(kind=effect.surface, rounds_left=effect.rounds, source_id=ctx.caster_id)
    ctx.emit([ZoneSurfaceAdded(zone_id=zone_id, surface=surface)])


def _zone_of(ctx: CastContext, creature_id: str) -> str | None:
    enc = ctx.state.encounter
    combatant = enc.combatants.get(creature_id) if enc is not None else None
    return combatant.zone_id if combatant is not None else None


def _splash(ctx: CastContext, effect: MultiTargetEffect, target_id: str) -> None:
    zone = _zone_of(ctx, target_id)
    if zone is None:
        return
    exclude = {ctx.caster_id} if effect.include_target else {ctx.caster_id, target_id}
    for cid in area_creatures(ctx.state, zone, effect.area, exclude):
        run_effects(ctx, effect.effects, cid, shared=True)


def run_effects(
    ctx: CastContext,
    effects: Sequence[Effect],
    target_id: str,
    *,
    crit: bool = False,
    half: bool = False,
    shared: bool = False,
) -> None:
    for effect in effects:
        if half and not isinstance(effect, DamageEffect):
            continue
        match effect:
            case AttackRollEffect():
                _attack(ctx, effect, target_id, shared)
            case SaveEffect():
                _save(ctx, effect, target_id, shared)
            case DamageEffect():
                _damage(ctx, effect, target_id, crit, half, shared)
            case HealEffect() | TempHpEffect():
                _heal(ctx, effect, target_id, shared)
            case ApplyConditionEffect() | AcBuffEffect():
                _condition(ctx, effect, target_id)
            case RemoveConditionEffect():
                for name in effect.conditions:
                    ctx.emit(remove_condition(ctx.state.creatures[target_id], name))
            case SurfaceEffect():
                zone = _zone_of(ctx, target_id)
                if zone is not None:
                    place_surface(ctx, effect, zone)
            case MultiTargetEffect():
                _splash(ctx, effect, target_id)
