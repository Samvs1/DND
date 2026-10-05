"""Party-side AI (M3.10): the safe default for an absent player and a simple autoplay.

- `safe_default_turn(state, creature_id) -> list[AnyCommand]` (SPEC 10: on a turn timeout or a
  disconnect the engine plays a safe default): a creature with no standing ally in its zone
  Dashes toward the nearest one (as far along the cheapest path as the doubled movement
  reaches, standing up first costs half its speed); otherwise it Dodges. No action (down,
  surprised, incapacitated): it just ends the turn. Always ends with `EndTurnCommand`.
- `next_pc_command(state, creature_id, regs, rng)` / `auto_pc_turn(...)` (the whole plan): a
  simple party autoplay for the headless sim and later companions, through the same planner as
  the monsters (`rules.ai_plan`): stand up when prone; with a dying ally, the bonus action first
  (Healing Word, a potion handed over in its zone); then the action (the best weapon attack or
  spell: damage, kill chance, target threat, concentration breaking, healing a dying ally with an
  action spell), further attacks of the Attack action, the bonus action (off-hand attack, bonus
  spells, potions); approach when nothing reaches, Dodge when nothing helps; a ranged creature
  steps away from enemies after acting. The party never flees on its own.

Public API: `safe_default_turn`, `next_pc_command`, `auto_pc_turn`.
"""

from aidm.data.combat_data import CombatRegistries
from aidm.models.commands import (
    AnyCommand,
    DashCommand,
    DodgeCommand,
    EndTurnCommand,
    MoveCommand,
)
from aidm.models.encounter import Encounter
from aidm.models.state import GameState
from aidm.rules.ai_options import AiChoice, Phase, pc_choices, prefers_range
from aidm.rules.ai_plan import (
    Chooser,
    approach_step,
    best_action_step,
    dry_run,
    plan_turn,
    reposition_step,
    stand_step,
)
from aidm.rules.ai_view import AiView, ai_view
from aidm.rules.combat_moves import PRONE
from aidm.rules.conditions import effective_speed
from aidm.rules.dice import Rng
from aidm.rules.zones import zone_path


def _ally_zones(state: GameState, enc: Encounter, creature_id: str) -> list[str]:
    me = enc.combatant(creature_id)
    zones: set[str] = set()
    for cid, combatant in enc.combatants.items():
        creature = state.creatures.get(cid)
        if cid == creature_id or creature is None or creature.dead or creature.hp <= 0:
            continue
        if combatant.side is me.side and combatant.withdrawn is None:
            zones.add(combatant.zone_id)
    return sorted(zones)


def _dash_toward(state: GameState, enc: Encounter, creature_id: str, goal: str) -> list[AnyCommand]:
    creature, combatant = state.creatures[creature_id], enc.combatant(creature_id)
    speed = effective_speed(creature)
    budget = combatant.economy.movement_left + speed
    if any(c.name == PRONE for c in creature.conditions):
        budget -= creature.speed // 2
    path = zone_path(enc.zone_map, combatant.zone_id, goal)
    dest = combatant.zone_id
    for zone in path.zones:
        if zone_path(enc.zone_map, combatant.zone_id, zone).feet <= budget:
            dest = zone
    plan: list[AnyCommand] = [DashCommand(actor_id=creature_id)]
    if dest != combatant.zone_id:
        plan.append(MoveCommand(actor_id=creature_id, zone_id=dest))
    return plan


def safe_default_turn(state: GameState, creature_id: str) -> list[AnyCommand]:
    enc = state.encounter
    if enc is None or enc.active_id() != creature_id:
        return []
    end = EndTurnCommand(actor_id=creature_id)
    creature, combatant = state.creatures[creature_id], enc.combatant(creature_id)
    if creature.hp <= 0 or not combatant.economy.action:
        return [end]
    zones = _ally_zones(state, enc, creature_id)
    here = combatant.zone_id
    if zones and here not in zones and effective_speed(creature) > 0:
        goal = min(zones, key=lambda z: (zone_path(enc.zone_map, here, z).feet, z))
        return [*_dash_toward(state, enc, creature_id, goal), end]
    return [DodgeCommand(actor_id=creature_id), end]


def _chooser(regs: CombatRegistries, phase: Phase) -> Chooser:
    def choose(state: GameState, view: AiView) -> list[AiChoice]:
        return pc_choices(state, view, regs, phase)

    return choose


def _dying_ally(state: GameState, view: AiView) -> bool:
    return any(state.creatures[a].hp == 0 and not state.creatures[a].stable for a in view.allies)


def _action_phase(
    state: GameState, view: AiView, regs: CombatRegistries, rng: Rng, ranged: bool
) -> AnyCommand | None:
    step = best_action_step(state, view, regs, rng, _chooser(regs, "action"), ranged=ranged)
    if step is not None:
        return step
    step = approach_step(state, view, regs)
    if step is not None:
        return step
    dodge = DodgeCommand(actor_id=view.actor_id)
    return dodge if view.enemies and dry_run(state, dodge, regs) is not None else None


def next_pc_command(
    state: GameState, creature_id: str, regs: CombatRegistries, rng: Rng
) -> AnyCommand | None:
    enc = state.encounter
    if enc is None or enc.active_id() != creature_id:
        return None
    view = ai_view(state, creature_id, regs)
    end = EndTurnCommand(actor_id=creature_id)
    combatant = enc.combatant(creature_id)
    if view is None or state.creatures[creature_id].hp <= 0 or combatant.withdrawn is not None:
        return end
    economy = combatant.economy
    ranged = prefers_range(state, creature_id, regs)
    bonus = _chooser(regs, "bonus")
    steps = [lambda: stand_step(state, view, regs)]
    if economy.bonus_action and _dying_ally(state, view):
        steps.append(lambda: best_action_step(state, view, regs, rng, bonus, ranged=ranged))
    if economy.action:
        steps.append(lambda: _action_phase(state, view, regs, rng, ranged))
    elif economy.attacks_left > 0:
        attack = _chooser(regs, "attack")
        steps.append(lambda: best_action_step(state, view, regs, rng, attack, ranged=ranged))
    if economy.bonus_action:
        steps.append(
            lambda: best_action_step(state, view, regs, rng, bonus, ranged=ranged, move=False)
        )
    steps.append(lambda: reposition_step(state, view, regs, ranged=ranged))
    for step in steps:
        command = step()
        if command is not None:
            return command
    return end


def auto_pc_turn(
    state: GameState, creature_id: str, regs: CombatRegistries, rng: Rng
) -> list[AnyCommand]:
    return plan_turn(state, creature_id, regs, rng, next_pc_command)
