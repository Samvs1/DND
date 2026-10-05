"""The combat AI's planning core (M3.10), shared by monsters and party creatures.

A turn is planned ONE command at a time from the current state (`plan_turn` chains the steps
over projected dry runs to show a whole plan). Every command the planner returns has been
dry-run through `rules.commands.execute_command` with a probe RNG, so it is never refused in the
state it was planned for; when nothing valid remains the step is `EndTurnCommand`.
- `best_action_step`: the best (zone, option) pair: options are scored from the current zone and
  from every zone the movement left reaches (each reached zone is the projected state of a dry-run
  move), plus the zone's position value for the creature's role, minus a small cost for moving.
  The first command is the move (when the best zone is elsewhere) or the option itself. Equal
  best values are broken with the injected RNG (deterministic for a seed).
- `approach_step`: no option anywhere in reach: move to the reachable zone closest (path feet) to
  the nearest enemy, else Dash (the next step moves again).
- `reposition_step`: after acting, a ranged creature sharing its zone with an enemy steps to a
  better zone for its role (no enemy there, high ground, cover).
- `retreat_step`: a broken creature leaves: Flee when no enemy shares its zone, else move to the
  reachable enemy-free zone farthest from the enemies, else Dash. Disengage is not used:
  opportunity attacks are Tier 2, so it would change nothing.
- `stand_step`: a prone creature with the movement to spare stands up first.

Public API: `ProbeRng`, `dry_run(state, command, regs) -> list[AnyEvent] | None`, `StepFn`,
`Chooser` (state, view -> valued choices),
`plan_turn`, `best_action_step`, `approach_step`, `reposition_step`, `retreat_step`,
`stand_step`, `position_value`, `zone_distance`, `MIN_VALUE`.
"""

from collections.abc import Callable
from dataclasses import replace

from aidm.data.combat_data import CombatRegistries
from aidm.models.commands import (
    AnyCommand,
    DashCommand,
    EndTurnCommand,
    FleeCommand,
    MoveCommand,
)
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.zones import CoverLevel
from aidm.rules.ai_options import AiChoice
from aidm.rules.ai_view import AiView
from aidm.rules.combat_moves import PRONE
from aidm.rules.command_checks import CommandRefused
from aidm.rules.commands import execute_command
from aidm.rules.conditions import effective_speed
from aidm.rules.dice import Rng
from aidm.rules.projection import project_state
from aidm.rules.zones import reachable_zones, zone_path

MIN_VALUE = 0.05
_MOVE_COST = 0.25
_REPOSITION_GAIN = 0.5
_MAX_PLAN = 12
_COVER_VALUE = {CoverLevel.NONE: 0.0, CoverLevel.HALF: 0.5, CoverLevel.THREE_QUARTERS: 1.0}
_TIE = 1e-9
_FAR = 10_000

type StepFn = Callable[[GameState, str, CombatRegistries, Rng], AnyCommand | None]
type Chooser = Callable[[GameState, AiView], list[AiChoice]]


class ProbeRng:
    """A fixed RNG for dry runs: validation happens before any roll, the outcome is discarded."""

    def randint(self, a: int, b: int, /) -> int:
        return a


_PROBE = ProbeRng()


def dry_run(state: GameState, command: AnyCommand, regs: CombatRegistries) -> list[AnyEvent] | None:
    try:
        return execute_command(state, command, regs, _PROBE)
    except CommandRefused:
        return None


def plan_turn(
    state: GameState, creature_id: str, regs: CombatRegistries, rng: Rng, step: StepFn
) -> list[AnyCommand]:
    plan: list[AnyCommand] = []
    hypo = state
    for _ in range(_MAX_PLAN):
        command = step(hypo, creature_id, regs, rng)
        if command is None:
            return plan
        plan.append(command)
        if isinstance(command, (EndTurnCommand, FleeCommand)):
            break
        events = dry_run(hypo, command, regs)
        if events is None:
            plan[-1] = EndTurnCommand(actor_id=creature_id)
            return plan
        hypo = project_state(hypo, events)
    if not plan or not isinstance(plan[-1], EndTurnCommand):
        plan.append(EndTurnCommand(actor_id=creature_id))
    return plan


def zone_distance(state: GameState, zone_id: str, others: tuple[str, ...]) -> int:
    enc = state.encounter
    if enc is None or not others:
        return _FAR
    zones = {enc.combatant(cid).zone_id for cid in others}
    return min(zone_path(enc.zone_map, zone_id, z).feet for z in sorted(zones))


def _enemies_in(state: GameState, view: AiView, zone_id: str) -> int:
    enc = state.encounter
    if enc is None:
        return 0
    return sum(1 for cid in view.enemies if enc.combatant(cid).zone_id == zone_id)


def position_value(state: GameState, view: AiView, zone_id: str, ranged: bool) -> float:
    enc = state.encounter
    if enc is None or not ranged:
        return 0.0
    zone = enc.zone_map.zone(zone_id)
    value = (1.0 if zone.high_ground else 0.0) + _COVER_VALUE[zone.cover]
    return value - 2.0 * _enemies_in(state, view, zone_id)


def _reachable(
    state: GameState, view: AiView, regs: CombatRegistries
) -> list[tuple[str, MoveCommand | None, GameState]]:
    enc = state.encounter
    out: list[tuple[str, MoveCommand | None, GameState]] = [(view.zone_id, None, state)]
    if enc is None:
        return out
    left = enc.combatant(view.actor_id).economy.movement_left
    if left <= 0:
        return out
    for zone in sorted(reachable_zones(enc.zone_map, view.zone_id, left)):
        if zone == view.zone_id:
            continue
        move = MoveCommand(actor_id=view.actor_id, zone_id=zone)
        events = dry_run(state, move, regs)
        if events is None:
            continue
        hypo = project_state(state, events)
        if hypo.creatures[view.actor_id].hp > 0:
            out.append((zone, move, hypo))
    return out


def _pick(
    scored: list[tuple[float, int, AnyCommand, AnyCommand, GameState]],
    regs: CombatRegistries,
    rng: Rng,
) -> AnyCommand | None:
    scored.sort(key=lambda s: (-s[0], s[1]))
    valid: list[tuple[float, AnyCommand]] = []
    for total, _, first, action, hypo in scored:
        if valid and total < valid[0][0] - _TIE:
            break
        if dry_run(hypo, action, regs) is not None:
            valid.append((total, first))
    if not valid:
        return None
    return valid[rng.randint(0, len(valid) - 1)][1] if len(valid) > 1 else valid[0][1]


def best_action_step(
    state: GameState,
    view: AiView,
    regs: CombatRegistries,
    rng: Rng,
    chooser: Chooser,
    *,
    ranged: bool,
    move: bool = True,
) -> AnyCommand | None:
    zones = _reachable(state, view, regs) if move else [(view.zone_id, None, state)]
    scored: list[tuple[float, int, AnyCommand, AnyCommand, GameState]] = []
    for order, (zone, step, hypo) in enumerate(zones):
        here = replace(view, zone_id=zone)
        bonus = position_value(hypo, here, zone, ranged) - (_MOVE_COST if step else 0.0)
        for choice in chooser(hypo, here):
            if choice.value > MIN_VALUE:
                first = step or choice.command
                scored.append((choice.value + bonus, order, first, choice.command, hypo))
    return _pick(scored, regs, rng)


def approach_step(state: GameState, view: AiView, regs: CombatRegistries) -> AnyCommand | None:
    enc = state.encounter
    if enc is None or not view.enemies:
        return None
    here = zone_distance(state, view.zone_id, view.enemies)
    options = [
        (zone_distance(state, z, view.enemies), z, m) for z, m, _ in _reachable(state, view, regs)
    ]
    best = min(options, key=lambda o: (o[0], o[1]))
    if best[2] is not None and best[0] < here:
        return best[2]
    economy = enc.combatant(view.actor_id).economy
    creature = state.creatures[view.actor_id]
    if here > 0 and economy.action and effective_speed(creature) > 0:
        dash = DashCommand(actor_id=view.actor_id)
        return dash if dry_run(state, dash, regs) is not None else None
    return None


def reposition_step(
    state: GameState, view: AiView, regs: CombatRegistries, *, ranged: bool
) -> AnyCommand | None:
    if not ranged or _enemies_in(state, view, view.zone_id) == 0:
        return None
    here = position_value(state, view, view.zone_id, True)
    best: tuple[float, MoveCommand | None] = (here + _REPOSITION_GAIN, None)
    for zone, move, hypo in _reachable(state, view, regs):
        value = position_value(hypo, replace(view, zone_id=zone), zone, True)
        if move is not None and value > best[0]:
            best = (value, move)
    return best[1]


def retreat_step(state: GameState, view: AiView, regs: CombatRegistries) -> AnyCommand | None:
    flee = FleeCommand(actor_id=view.actor_id)
    if dry_run(state, flee, regs) is not None:
        return flee
    safe = [
        (zone_distance(hypo, zone, view.enemies), zone, move)
        for zone, move, hypo in _reachable(state, view, regs)
        if move is not None and _enemies_in(hypo, view, zone) == 0
    ]
    if safe:
        return max(safe, key=lambda s: (s[0], s[1]))[2]
    dash = DashCommand(actor_id=view.actor_id)
    return dash if dry_run(state, dash, regs) is not None else None


def stand_step(state: GameState, view: AiView, regs: CombatRegistries) -> AnyCommand | None:
    creature = state.creatures[view.actor_id]
    if not any(c.name == PRONE for c in creature.conditions):
        return None
    stand = MoveCommand(actor_id=view.actor_id, zone_id=view.zone_id)
    return stand if dry_run(state, stand, regs) is not None else None
