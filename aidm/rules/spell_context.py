"""The state of one cast while the spell effect interpreter runs (`rules.spell_effects`).

`aidm.rules.spells.cast_spell` builds one `CastContext` per cast; every effect handler reads and
extends it. `emit` keeps a projected state (`rules.projection`) so later effects see earlier ones.

Public API:
- `CastContext(rng, spell, caster_id, cast_level, numbers, char_level, feats, state, name,
  target_zone, ...)`: `target_zone` is the zone a "point" or area spell chose; `rolls` holds
  shared rolls (area spells: one roll for every target), `pools` what is left of each HP pool.
- `cast_dice(effect_dice, ctx, *, cantrip_scaling, upcast_dice, add_modifier) -> str`: the dice
  of an effect at this cast (cantrip tiers at character levels 5/11/17, `upcast_dice` once per
  slot level above the spell's level, the spellcasting modifier).
- `cast_roll(ctx, effect, dice, *, crit, shared) -> Roll`: rolls (and logs) the dice once, or
  reuses the shared roll of the same effect.
- `spell_attack_profile(spell, name, ctx) -> AttackProfile`; `cast_zone_of(ctx, creature_id)
  -> str | None` (None outside a fight).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from aidm.data.feature_defs import FeatureDef
from aidm.data.registry import Registry
from aidm.data.spell_defs import Effect, SpellDef
from aidm.models.combat import AttackEconomy, AttackProfile
from aidm.models.conditions import ConditionLink
from aidm.models.dice import Roll
from aidm.models.events import AnyEvent, DiceRolled
from aidm.models.state import GameState
from aidm.rules.dice import Rng, parse_dice, roll
from aidm.rules.projection import project_state
from aidm.rules.spell_targets import CasterNumbers, spell_band

CANTRIP_TIERS = (5, 11, 17)


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
    target_zone: str | None = None
    events: list[AnyEvent] = field(default_factory=list[AnyEvent])
    links: list[ConditionLink] = field(default_factory=list[ConditionLink])
    rolls: dict[int, Roll] = field(default_factory=dict[int, Roll])
    pools: dict[int, int] = field(default_factory=dict[int, int])
    surfaces: set[tuple[str, str]] = field(default_factory=set[tuple[str, str]])
    zone_hits: set[tuple[str, str]] = field(default_factory=set[tuple[str, str]])

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


def cast_roll(ctx: CastContext, effect: Effect, dice: str, *, crit: bool, shared: bool) -> Roll:
    key = id(effect)
    if shared and key in ctx.rolls:
        return ctx.rolls[key]
    rolled = roll(dice, ctx.rng, crit=crit)
    ctx.emit([DiceRolled(roll=rolled, roller_id=ctx.caster_id, label=ctx.name or ctx.spell.index)])
    if shared:
        ctx.rolls[key] = rolled
    return rolled


def cast_zone_of(ctx: CastContext, creature_id: str) -> str | None:
    enc = ctx.state.encounter
    combatant = enc.combatants.get(creature_id) if enc is not None else None
    return combatant.zone_id if combatant is not None else None
