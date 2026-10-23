"""Spell aiming for the combat AI (M3.10): where a spell does the most good, by the DSL alone.

`spell_aims(state, view, caster_id, spell, numbers, regs)` lists the ways to cast one spell from
the caster's current zone, each with a value (`rules.ai_view` units), best first:
- "area" spells: every zone it can be aimed at (`rules.spell_targets.area_zones`); the value
  sums every creature the area hits, allies included (`ally_loss`), so a breath weapon or a
  Fireball avoids friends when it can;
- "creature": one target; "creatures": up to `instance_count` targets: distinct creatures by
  value, or (`repeat`, darts and beams) instances given greedily to the best marginal target so
  the excess over a kill spills to the next one;
- hostile spells (damage, saves, attack rolls, harmful conditions) aim at enemies; the others
  (healing, buffs) at allies and the caster. Targets outside the spell's band or its
  `creature_types` are skipped; "self", "point" and dead-target spells are not aimed (the AI
  does not cast them).
`spell_cost(spell, caster)`: the value a cast must beat: slots are worth keeping (3 per spell
level) and a new concentration spell ends the current one.

Public API: `SpellAim(target_ids, target_zone, value)`, `spell_aims`, `spell_cost`,
`is_hostile_spell(spell) -> bool`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from aidm.data.combat_data import CombatRegistries
from aidm.data.spell_defs import (
    ApplyConditionEffect,
    AttackRollEffect,
    DamageEffect,
    Effect,
    SaveEffect,
    SpellDef,
)
from aidm.models.state import Creature, GameState
from aidm.rules.ai_estimates import EffectEstimate, SpellNumbers, condition_harm, effects_estimate
from aidm.rules.ai_view import (
    AiView,
    ally_loss,
    buff_value,
    control_value,
    damage_value,
    heal_value,
)
from aidm.rules.monster_stats import creature_type_of
from aidm.rules.spell_targets import area_creatures, area_zones, instance_count, spell_band
from aidm.rules.zones import zone_range_check

_SLOT_VALUE = 3.0
_CONCENTRATION_SWAP = 4.0


@dataclass(frozen=True)
class SpellAim:
    target_ids: tuple[str, ...]
    target_zone: str | None
    value: float


def _hostile_effect(effect: Effect) -> bool:
    if isinstance(effect, (AttackRollEffect, SaveEffect, DamageEffect)):
        return True
    return isinstance(effect, ApplyConditionEffect) and condition_harm(effect.condition) > 0


def is_hostile_spell(spell: SpellDef) -> bool:
    return any(_hostile_effect(e) for e in spell.effects)


def spell_cost(spell: SpellDef, caster: Creature) -> float:
    cost = _SLOT_VALUE * spell.level
    if spell.concentration and caster.concentrating_on is not None:
        cost += _CONCENTRATION_SWAP
    return cost


def _scaled(est: EffectEstimate, k: int) -> EffectEstimate:
    return EffectEstimate(est.damage * k, est.heal * k, min(1.0, est.control * k), est.buff * k)


def _est_value(view: AiView, target: Creature, est: EffectEstimate) -> float:
    if target.id in view.enemies:
        hurt = damage_value(view, target, est.damage) + control_value(view, target, est.control)
        return hurt - 0.5 * heal_value(view, target, est.heal)
    if target.id == view.actor_id or target.id in view.allies:
        harm = ally_loss(view, target, est.damage) + 1.5 * control_value(view, target, est.control)
        good = heal_value(view, target, est.heal) + buff_value(view, target, est.buff)
        return good - harm
    return 0.0


type _Estimator = Callable[[str], EffectEstimate]


def _estimator(
    state: GameState, caster_id: str, spell: SpellDef, numbers: SpellNumbers, regs: CombatRegistries
) -> _Estimator:
    cache: dict[str, EffectEstimate] = {}
    feats = regs.chars.features

    def estimate(cid: str) -> EffectEstimate:
        if cid not in cache:
            cache[cid] = effects_estimate(state, caster_id, cid, spell.effects, numbers, feats)
        return cache[cid]

    return estimate


def _area_aims(state: GameState, view: AiView, spell: SpellDef, est: _Estimator) -> list[SpellAim]:
    enc = state.encounter
    if enc is None:
        return []
    zones = area_zones(enc.zone_map, view.zone_id, spell)
    area = spell.targeting.area or "zone"
    aims: list[SpellAim] = []
    for zone in zones:
        hit = area_creatures(state, zone, area, {view.actor_id})
        value = sum(_est_value(view, state.creatures[cid], est(cid)) for cid in hit)
        aims.append(SpellAim((), zone, value))
    return aims


def _in_band(state: GameState, view: AiView, spell: SpellDef, cid: str) -> bool:
    enc = state.encounter
    if enc is None or cid not in enc.combatants:
        return False
    kinds = spell.targeting.creature_types
    if kinds and creature_type_of(state.creatures[cid]) not in kinds:
        return False
    zone = enc.combatant(cid).zone_id
    return zone_range_check(enc.zone_map, view.zone_id, zone, spell_band(spell)).in_range


def _repeat_targets(
    state: GameState, view: AiView, pool: Sequence[str], allowed: int, est: _Estimator
) -> SpellAim:
    counts = dict.fromkeys(pool, 0)
    total = 0.0
    for _ in range(allowed):

        def gain(cid: str) -> float:
            creature, k = state.creatures[cid], counts[cid]
            before = _est_value(view, creature, _scaled(est(cid), k)) if k else 0.0
            return _est_value(view, creature, _scaled(est(cid), k + 1)) - before

        best = max(pool, key=gain)
        total += gain(best)
        counts[best] += 1
    chosen = tuple(cid for cid in pool for _ in range(counts[cid]))
    return SpellAim(chosen, None, total)


def _creature_aims(
    state: GameState, view: AiView, spell: SpellDef, numbers: SpellNumbers, est: _Estimator
) -> list[SpellAim]:
    pool_ids = view.enemies if is_hostile_spell(spell) else (view.actor_id, *view.allies)
    pool = [cid for cid in pool_ids if _in_band(state, view, spell, cid)]
    if not pool:
        return []
    single = {cid: _est_value(view, state.creatures[cid], est(cid)) for cid in pool}
    if spell.targeting.kind == "creature":
        return [SpellAim((cid,), None, value) for cid, value in single.items()]
    allowed = instance_count(spell, spell.level, numbers.char_level)
    if spell.targeting.repeat:
        return [_repeat_targets(state, view, pool, allowed, est)]
    ranked = sorted((cid for cid in pool if single[cid] > 0), key=lambda c: -single[c])
    chosen = tuple(ranked[:allowed])
    return [SpellAim(chosen, None, sum(single[c] for c in chosen))] if chosen else []


def spell_aims(
    state: GameState,
    view: AiView,
    caster_id: str,
    spell: SpellDef,
    numbers: SpellNumbers,
    regs: CombatRegistries,
) -> list[SpellAim]:
    targeting = spell.targeting
    if targeting.dead or targeting.kind in ("self", "point"):
        return []
    est = _estimator(state, caster_id, spell, numbers, regs)
    if targeting.kind == "area":
        aims = _area_aims(state, view, spell, est)
    else:
        aims = _creature_aims(state, view, spell, numbers, est)
    return sorted(aims, key=lambda a: -a.value)
