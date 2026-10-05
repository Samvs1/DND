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
- surface: placed once per zone and surface for the cast through `rules.surfaces` (interactions,
  "create" harms), carrying the caster's spell DC, the upcast levels and the concentration link.
- damage also hits the target's zone: a matching surface damage interaction fires once per zone
  and damage type per cast (fire into oil ignites); area spells hit their zone even when empty.
- multi_target: the sub-effects run on every other creature of the current target's zone (or
  zone and neighbours), sharing rolls.
- hp_pool, stabilize, revive, teleport: `rules.spell_special` (the pool decides who its
  sub-effects reach). The cast state itself (`CastContext`, dice, shared rolls) lives in
  `rules.spell_context`.

Public API: `run_effects(ctx, effects, target_id, *, crit=False, half=False, shared=False) -> None`,
`place_surface(ctx, effect, zone_id) -> None`, `zone_damage(ctx, zone_id, damage_type) -> None`,
`damage_types(effects) -> list[str]`.
"""

from collections.abc import Sequence

from aidm.data.spell_defs import (
    AcBuffEffect,
    ApplyConditionEffect,
    AttackRollEffect,
    DamageEffect,
    Effect,
    HealEffect,
    HpPoolEffect,
    MultiTargetEffect,
    RemoveConditionEffect,
    ReviveEffect,
    SaveEffect,
    StabilizeEffect,
    SurfaceEffect,
    TeleportEffect,
    TempHpEffect,
)
from aidm.models.abilities import Ability
from aidm.models.conditions import ConditionLink, SaveEnds
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.events import CheckResolved, TempHpSet
from aidm.models.zones import ZoneSurface
from aidm.rules.attacks import deal_damage, roll_attack
from aidm.rules.concentration import concentration_upkeep
from aidm.rules.condition_timing import apply_condition, new_condition, remove_condition
from aidm.rules.conditions import save_with_conditions
from aidm.rules.damage import resolve_healing
from aidm.rules.features import healing_bonus, save_advantage_sources
from aidm.rules.spell_context import (
    CastContext,
    cast_dice,
    cast_roll,
    cast_zone_of,
    spell_attack_profile,
)
from aidm.rules.spell_special import (
    pool_admits,
    revive_target,
    stabilize_target,
    teleport_target,
)
from aidm.rules.spell_targets import area_creatures
from aidm.rules.surface_state import surface_def
from aidm.rules.surfaces import place_surface_events, zone_damage_events

MAGIC_TAG = "magic"


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
    total = cast_roll(ctx, effect, dice, crit=crit, shared=shared).total
    amount = max(0, total) // 2 if half else total
    packet = DamagePacket(amount=amount, damage_type=DamageType(effect.damage_type))
    ctx.emit(
        deal_damage(
            ctx.rng, ctx.state, ctx.caster_id, target_id, [packet], crit=crit, feats=ctx.feats
        )
    )
    zone = cast_zone_of(ctx, target_id)
    if zone is not None:
        zone_damage(ctx, zone, effect.damage_type)


def zone_damage(ctx: CastContext, zone_id: str, damage_type: str) -> None:
    if (zone_id, damage_type) in ctx.zone_hits:
        return
    ctx.zone_hits.add((zone_id, damage_type))
    ctx.emit(zone_damage_events(ctx.rng, ctx.state, zone_id, damage_type))


def damage_types(effects: Sequence[Effect]) -> list[str]:
    found: list[str] = []
    for effect in effects:
        if isinstance(effect, DamageEffect):
            found.append(effect.damage_type)
        elif isinstance(effect, AttackRollEffect):
            found.extend(damage_types(effect.on_hit))
        elif isinstance(effect, (MultiTargetEffect, HpPoolEffect)):
            found.extend(damage_types(effect.effects))
        elif isinstance(effect, SaveEffect):
            found.extend(damage_types(effect.on_fail))
    return list(dict.fromkeys(found))


def _heal(
    ctx: CastContext, effect: HealEffect | TempHpEffect, target_id: str, shared: bool
) -> None:
    dice = cast_dice(
        effect.dice, ctx, upcast_dice=effect.upcast_dice, add_modifier=effect.add_modifier
    )
    amount = cast_roll(ctx, effect, dice, crit=False, shared=shared).total
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


def _save_tags(effects: Sequence[Effect], magical: bool) -> set[str]:
    tags = {MAGIC_TAG} if magical else set[str]()
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
    sources = save_advantage_sources(
        target, ctx.feats, ability, _save_tags(effect.on_fail, ctx.magical)
    )
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
    sdef = surface_def(effect.surface)
    default = sdef.duration_rounds if sdef is not None else None
    surface = ZoneSurface(
        kind=effect.surface,
        rounds_left=effect.rounds or ctx.spell.duration_rounds or default,
        source_id=ctx.caster_id,
        dc=ctx.numbers.save_dc,
        upcast=max(0, ctx.cast_level - ctx.spell.level),
        concentration=ctx.spell.concentration,
    )
    ctx.emit(place_surface_events(ctx.rng, ctx.state, zone_id, surface))


def _splash(ctx: CastContext, effect: MultiTargetEffect, target_id: str) -> None:
    zone = cast_zone_of(ctx, target_id)
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
                zone = cast_zone_of(ctx, target_id)
                if zone is not None:
                    place_surface(ctx, effect, zone)
            case MultiTargetEffect():
                _splash(ctx, effect, target_id)
            case HpPoolEffect():
                if pool_admits(ctx, effect, target_id):
                    run_effects(ctx, effect.effects, target_id, shared=shared)
            case StabilizeEffect():
                stabilize_target(ctx, target_id)
            case ReviveEffect():
                revive_target(ctx, effect, target_id)
            case TeleportEffect():
                teleport_target(ctx, target_id)
