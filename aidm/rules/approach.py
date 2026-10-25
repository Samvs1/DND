"""Approach then strike (M36.2, round 6 Y10: a melee attack at a foe out of reach was refused or
swapped to the bow). Pure: plans the move commands, never runs them.

A strike needs the target inside the attack's range band (`rules.zones`: melee = the same zone).
When it is not, the hero walks with the movement left this turn (no Dash: the action is kept for
the strike) to the cheapest zone from which the band reaches the target (ties by zone id). Every
candidate move is checked with the real `move` command on the state (standing up from prone,
rough ground, speed 0 refuse it), so the plan is exactly what the Move button would allow.
Never a swap to another weapon.

Public API:
- `MovePlan(moves, feet)`: the commands (empty = already in reach) and the feet walked.
- `plan_into_band(state, actor_id, target_id, band, regs) -> MovePlan | None`: None when no zone
  in reach of the target can be reached this turn (or there is no fight / no such combatant).
- `approach_moves(state, actor_id, target_id, profile, regs) -> list[MoveCommand] | None`: the
  plan for an attack option (`AttackProfile`): [] already in reach, the moves, or None.
"""

from dataclasses import dataclass

from aidm.data.combat_data import CombatRegistries
from aidm.models.combat import AttackProfile
from aidm.models.commands import MoveCommand
from aidm.models.state import GameState
from aidm.models.zones import RangeBand
from aidm.rules.ai_plan import dry_run
from aidm.rules.zones import MELEE_BAND, range_band, reachable_zones, zone_range_check


@dataclass(frozen=True)
class MovePlan:
    moves: tuple[MoveCommand, ...]
    feet: int


def profile_band(profile: AttackProfile) -> RangeBand:
    if not profile.ranged:
        return MELEE_BAND
    return range_band(profile.range_normal, profile.range_long)


def plan_into_band(
    state: GameState, actor_id: str, target_id: str, band: RangeBand, regs: CombatRegistries
) -> MovePlan | None:
    enc = state.encounter
    if enc is None or actor_id not in enc.combatants or target_id not in enc.combatants:
        return None
    zmap = enc.zone_map
    me, goal = enc.combatant(actor_id), enc.combatant(target_id).zone_id
    if zone_range_check(zmap, me.zone_id, goal, band).in_range:
        return MovePlan(moves=(), feet=0)
    reach = reachable_zones(zmap, me.zone_id, me.economy.movement_left)
    spots = sorted(
        (feet, zone)
        for zone, feet in reach.items()
        if zone != me.zone_id and zone_range_check(zmap, zone, goal, band).in_range
    )
    for feet, zone in spots:
        move = MoveCommand(actor_id=actor_id, zone_id=zone)
        if dry_run(state, move, regs) is not None:
            return MovePlan(moves=(move,), feet=feet)
    return None


def approach_moves(
    state: GameState,
    actor_id: str,
    target_id: str,
    profile: AttackProfile,
    regs: CombatRegistries,
) -> list[MoveCommand] | None:
    plan = plan_into_band(state, actor_id, target_id, profile_band(profile), regs)
    return list(plan.moves) if plan is not None else None
