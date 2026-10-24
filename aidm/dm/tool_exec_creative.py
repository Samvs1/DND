"""Executor for `creative_effect` (SPEC 6.1 creative actions, 6.3): severity -> engine numbers.

The model picks an `effect_kind` and a `severity`; the engine picks the dice (by party level),
the save DC, the duration cap, the condition's saving throw and the surface, all from
data/bg3/dm_tiers.json. Damage goes through the one damage path (`rules.attacks.deal_damage`).
A damaging, condition or push effect aimed at a non-hostile NPC stops at the point of no return;
confirmed (or aimed at a hostile NPC here) it starts the fight with them (M29.7c R15,
`tool_exec_rewards.fight_npcs`). One aimed at another player's hero is refused (a push is
allowed in a fight).
M27.6: an effect that leans on gear (`item`, or the gear the player's words name) goes through
`aidm.dm.creative_gear`: gear the hero lacks (or a keepsake) is refused and told as an attempt;
carried gear thrown at a creature of the fight is THE item interpreter's use, a substance the
target is weak to is THE weakness rule; otherwise the creative effect runs and the gear is kept.
M31.1a V3: creative damage never stands in for a weapon attack: with a weapon, or a line that
reads as a weapon attack, it is the engine's attack (`aidm.dm.creative_weapon`).

Public API: `run_creative_effect(state, args, ctx, rng, regs) -> ToolResult`.
"""

from aidm.dm.creative_gear import gear_outcome, leaned_gear
from aidm.dm.creative_weapon import weapon_outcome
from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import hostile_pending, npc_is_present, require_creature
from aidm.dm.tool_exec_rewards import fight_npcs
from aidm.dm.tools import CreativeEffectArgs
from aidm.models.abilities import Ability
from aidm.models.combat_events import CombatantMoved
from aidm.models.damage import DamagePacket
from aidm.models.dice import RollKind
from aidm.models.dm_tiers import EffectKind
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.events import AnyEvent, CheckResolved, DiceRolled
from aidm.models.state import Creature, GameState
from aidm.models.world import WorldNpc
from aidm.models.zones import ZoneSurface
from aidm.rules.attacks import deal_damage
from aidm.rules.condition_timing import apply_condition, new_condition
from aidm.rules.conditions import save_with_conditions
from aidm.rules.dice import Rng, roll
from aidm.rules.dm_tiers import party_level, severity_damage_dice, severity_rounds, severity_save_dc
from aidm.rules.projection import project_state
from aidm.rules.social import npc_is_hostile
from aidm.rules.surface_state import surface_removed_events, zone_surface
from aidm.rules.surfaces import enter_zone_events, place_surface_events
from aidm.rules.zones import zone_neighbors

_HOSTILE = {EffectKind.MINOR_DAMAGE, EffectKind.CONDITION, EffectKind.PUSH}
_ZONE = {EffectKind.DIFFICULT_TERRAIN, EffectKind.DARK, EffectKind.LIGHT}
ADVANTAGE_CONDITION = "helped"

type _Run = tuple[GameState, CreativeEffectArgs, Rng, ToolRegistries]


def _encounter(state: GameState) -> Encounter:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        raise ToolRefused("zone effects and pushes need an active fight")
    return enc


def _against_npc(run: _Run, npc: WorldNpc, ctx: ToolContext) -> ToolResult:
    """An attack on someone out of a fight: past the point of no return it starts the fight with
    them (M29.7c R15: a confirmed attack on an allied master only turned it hostile)."""
    state, args, rng, regs = run
    if not npc_is_present(state, npc):
        raise ToolRefused(f"{npc.name} is not here")
    if not npc_is_hostile(npc) and not ctx.confirm_hostile:
        return hostile_pending(ctx, [npc], "creative_effect")
    return fight_npcs(state, [npc], rng, regs, f"attacked by {args.actor}")


def _refuse_against_hero(state: GameState, args: CreativeEffectArgs, target: Creature) -> None:
    """Free text never harms a fellow hero (QA-02): no damage or condition, and no push
    outside a fight. Only the structured combat commands can hit an ally."""
    if target.pc is None or target.id == args.actor or args.effect_kind not in _HOSTILE:
        return
    in_fight = state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE
    if args.effect_kind is EffectKind.PUSH and in_fight:
        return
    raise ToolRefused(f"{target.name} is a fellow hero: a creative effect cannot harm them")


def _damage(run: _Run, target: Creature) -> ToolResult:
    state, args, rng, regs = run
    dice = severity_damage_dice(regs.tiers, args.severity, party_level(state))
    rolled = roll(dice, rng)
    packet = DamagePacket(amount=rolled.total, damage_type=args.damage_type)
    feats = regs.combat.chars.features
    hurt = deal_damage(rng, state, args.actor, target.id, [packet], crit=False, feats=feats)
    events: list[AnyEvent] = [
        DiceRolled(
            roll=rolled,
            roller_id=args.actor,
            label="Creative action",
            kind=RollKind.DAMAGE,
            target_id=target.id,
        )
    ]
    summary = f"{target.name} takes {rolled.total} {args.damage_type.value} damage"
    return ToolResult(events=tuple(events + hurt), summary=summary)


def _save(run: _Run, target: Creature, ability: Ability) -> tuple[bool, CheckResolved]:
    state, args, rng, regs = run
    dc = severity_save_dc(regs.tiers, args.severity)
    result = save_with_conditions(rng, target, ability, dc)
    event = CheckResolved(
        creature_id=target.id, result=result, reason="creative", source_id=args.actor
    )
    return result.success, event


def _condition(run: _Run, target: Creature) -> ToolResult:
    _, args, _, regs = run
    allowed = regs.tiers.creative_conditions
    if args.condition not in allowed:
        raise ToolRefused(f"condition must be one of: {', '.join(sorted(allowed))}")
    name = args.condition
    saved, check = _save(run, target, Ability(allowed[name]))
    if saved:
        return ToolResult(events=(check,), summary=f"{target.name} resists being {name}")
    rounds = severity_rounds(regs.tiers, args.severity, args.duration_rounds)
    mark = new_condition(name, source_id=args.actor, rounds=rounds)
    events = (check, *apply_condition(target, mark))
    return ToolResult(events=events, summary=f"{target.name} is {name} for {rounds} round(s)")


def _advantage(target: Creature, actor_id: str) -> ToolResult:
    events = apply_condition(target, new_condition(ADVANTAGE_CONDITION, source_id=actor_id))
    return ToolResult(events=tuple(events), summary=f"{target.name} gains advantage next attack")


def _push(run: _Run, target: Creature) -> ToolResult:
    state, args, rng, _ = run
    enc = _encounter(state)
    combatant = enc.combatants.get(target.id)
    if combatant is None:
        raise ToolRefused(f"{target.name} is not in the fight")
    options = zone_neighbors(enc.zone_map, combatant.zone_id)
    if not options:
        raise ToolRefused("there is nowhere to push them")
    saved, check = _save(run, target, Ability.STR)
    if saved:
        return ToolResult(events=(check,), summary=f"{target.name} holds their ground")
    to_zone = options[0][0]
    moved = CombatantMoved(
        creature_id=target.id, from_zone=combatant.zone_id, to_zone=to_zone, reason="push"
    )
    after = project_state(state, [check, moved])
    entered = enter_zone_events(rng, after, target.id, combatant.zone_id)
    return ToolResult(events=(check, moved, *entered), summary=f"{target.name} is pushed away")


def _zone_effect(run: _Run) -> ToolResult:
    state, args, rng, regs = run
    enc = _encounter(state)
    zone_id = args.target or enc.positions().get(args.actor, "")
    if not enc.zone_map.has_zone(zone_id):
        raise ToolRefused(f"unknown zone {zone_id!r}")
    if args.effect_kind is EffectKind.LIGHT:
        events: list[AnyEvent] = []
        for kind in regs.tiers.light_removes:
            if zone_surface(state, zone_id, kind) is not None:
                events.extend(surface_removed_events(state, zone_id, kind, "light"))
        return ToolResult(events=tuple(events), summary=f"light fills {zone_id}")
    kind = regs.tiers.zone_effect_surfaces[args.effect_kind.value]
    rounds = severity_rounds(regs.tiers, args.severity, args.duration_rounds)
    surface = ZoneSurface(kind=kind, rounds_left=rounds, source_id=args.actor)
    events = place_surface_events(rng, state, zone_id, surface)
    return ToolResult(events=tuple(events), summary=f"{kind} covers {zone_id} for {rounds} rounds")


def run_creative_effect(
    state: GameState, args: CreativeEffectArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    require_creature(state, args.actor)
    gear = leaned_gear(state, args.actor, args.item, ctx.player_text)  # M27.6: carried or refused
    outcome = gear_outcome(state, args, gear, rng, regs) if gear is not None else None
    if outcome is not None:
        return outcome
    blow = weapon_outcome(state, args, gear, ctx.player_text, rng, regs)  # M31.1a V3
    if blow is not None:
        return blow
    run: _Run = (state, args, rng, regs)
    kind = args.effect_kind
    if kind in _ZONE:
        return _zone_effect(run)
    target_id = args.target or args.actor
    npc = state.world.npcs.get(target_id)
    if npc is not None and kind in _HOSTILE and target_id not in state.creatures:
        return _against_npc(run, npc, ctx)
    target = require_creature(state, target_id)
    _refuse_against_hero(state, args, target)
    if kind is EffectKind.MINOR_DAMAGE:
        return _damage(run, target)
    if kind is EffectKind.CONDITION:
        return _condition(run, target)
    if kind is EffectKind.PUSH:
        return _push(run, target)
    return _advantage(target, args.actor)
