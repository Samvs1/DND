"""Spell effects about hit-point pools, life and position (used by `rules.spell_effects`).

Semantics (SRD 5.1 unless noted; docs/RULES_DECISIONS.md M3.6b):
- hp_pool: the pool (dice + upcast dice) is rolled once per cast and effect; target instances
  arrive in the order the targeting block gives (Sleep: lowest current HP first). A target at
  0 HP or dead is skipped; a target whose current HP fits in what is left uses it up and is
  affected (`pool_admits` True), else it is not.
- stabilize: a dying target becomes stable (`rules.death.stabilize`); anyone else: nothing.
- revive: a dead target is alive again (`CreatureRevived`) and healed to `hp` (healing from 0
  removes the 0-HP unconscious state and resets the death saves). BG3: no time limit.
- teleport: the target (the caster of a "point" spell) moves to the chosen zone without spending
  movement (`CombatantMoved` reason "teleport"); entering triggers the zone's surfaces.
- light_source: the target carries a lit light (`LightLit`); lit in a dark place it alerts the
  place, like a torch (`item_use._bookkeeping`).

Public API: `pool_admits(ctx, effect, target_id) -> bool`, `stabilize_target(ctx, target_id)`,
`revive_target(ctx, effect, target_id)`, `teleport_target(ctx, target_id)`,
`light_target(ctx, effect, target_id)` (all emit into ctx).
"""

from aidm.data.spell_defs import HpPoolEffect, LightSourceEffect, ReviveEffect
from aidm.models.combat_events import CombatantMoved, CreatureRevived
from aidm.models.item_events import LightLit, PlaceAlerted
from aidm.rules.damage import resolve_healing
from aidm.rules.death import stabilize
from aidm.rules.light import place_dark
from aidm.rules.spell_context import CastContext, cast_dice, cast_roll, cast_zone_of
from aidm.rules.surfaces import enter_zone_events


def pool_admits(ctx: CastContext, effect: HpPoolEffect, target_id: str) -> bool:
    key = id(effect)
    if key not in ctx.pools:
        dice = cast_dice(effect.dice, ctx, upcast_dice=effect.upcast_dice)
        ctx.pools[key] = cast_roll(ctx, effect, dice, crit=False, shared=True).total
    target = ctx.state.creatures[target_id]
    if target.dead or target.hp <= 0 or target.hp > ctx.pools[key]:
        return False
    ctx.pools[key] -= target.hp
    return True


def stabilize_target(ctx: CastContext, target_id: str) -> None:
    ctx.emit(stabilize(ctx.state.creatures[target_id]))


def revive_target(ctx: CastContext, effect: ReviveEffect, target_id: str) -> None:
    if not ctx.state.creatures[target_id].dead:
        return
    ctx.emit([CreatureRevived(creature_id=target_id)])
    ctx.emit(resolve_healing(ctx.state.creatures[target_id], effect.hp))


def teleport_target(ctx: CastContext, target_id: str) -> None:
    start = cast_zone_of(ctx, target_id)
    goal = ctx.target_zone
    if start is None or goal is None or goal == start:
        return
    moved = CombatantMoved(
        creature_id=target_id, from_zone=start, to_zone=goal, path=(start, goal), reason="teleport"
    )
    ctx.emit([moved])
    ctx.emit(enter_zone_events(ctx.rng, ctx.state, target_id, start))


def light_target(ctx: CastContext, effect: LightSourceEffect, target_id: str) -> None:
    ctx.emit([LightLit(creature_id=target_id, item=ctx.spell.index, reach=effect.reach)])
    world, node = ctx.state.world, ctx.state.world.current_node
    fresh = world.alerted != node or world.alerted_by != "light"
    if node is not None and fresh and place_dark(ctx.state):
        ctx.emit([PlaceAlerted(node=node, reason="light")])
