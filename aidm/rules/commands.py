"""THE combat command entry point: one structured command in, its events out (SPEC 6.1).

`execute_command(state, command, regs, rng)` validates the command (active fight, the actor's
open turn, conditions that forbid acting or moving, the economy, targets, range by zone, items,
spells) and resolves it. It returns the events for the session to apply; it never mutates.
Invalid input raises `CommandRefused(code, reason)` before any event exists, so nothing
(action, bonus action, movement, item, slot) is consumed. Lower-level refusals
(`EconomyRefused`, `EncounterRefused`, `ZoneError`) are converted to `CommandRefused` here.

Per-command rules live in `rules.combat_moves` (move, dash, disengage, jump, shove, flee),
`rules.combat_actions` (attack, throw, hide, help, dodge), `rules.items` (use_item) and
`rules.spells` (cast, the spell effect DSL), `rules.monster_actions` (a monster's stat block
actions: attacks, save actions, multiattack, its spell kit), `rules.feature_commands` (class and
race feature actions from the feature hooks). `end_turn` closes the actor's turn via
`rules.turns.end_turn`.

Public API: `execute_command(state, command, regs, rng) -> list[AnyEvent]`.
"""

from typing import assert_never

from aidm.data.combat_data import CombatRegistries
from aidm.models.commands import (
    AnyCommand,
    AttackCommand,
    CastCommand,
    DashCommand,
    DisengageCommand,
    DodgeCommand,
    EndTurnCommand,
    FeatureActionCommand,
    FleeCommand,
    HelpCommand,
    HideCommand,
    JumpCommand,
    MonsterActionCommand,
    MoveCommand,
    ShoveCommand,
    ThrowCommand,
    UseItemCommand,
)
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.combat_actions import (
    attack_command,
    dodge_command,
    help_command,
    hide_command,
    throw_command,
)
from aidm.rules.combat_moves import (
    dash_command,
    disengage_command,
    flee_command,
    jump_command,
    move_command,
    shove_command,
)
from aidm.rules.command_checks import acting, refusal_from
from aidm.rules.dice import Rng
from aidm.rules.encounter import EncounterRefused
from aidm.rules.feature_commands import feature_action_command
from aidm.rules.items import use_item_command
from aidm.rules.monster_actions import monster_action_command
from aidm.rules.spells import cast_command
from aidm.rules.turns import EconomyRefused, end_turn
from aidm.rules.zones import ZoneError


def _end_turn(state: GameState, cmd: EndTurnCommand, rng: Rng) -> list[AnyEvent]:
    acting(state, cmd.actor_id)
    return end_turn(rng, state)


def _dispatch(
    state: GameState, command: AnyCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    match command:
        case AttackCommand():
            return attack_command(state, command, regs, rng)
        case CastCommand():
            return cast_command(state, command, regs, rng)
        case MoveCommand():
            return move_command(state, command, regs, rng)
        case DashCommand():
            return dash_command(state, command, regs)
        case DisengageCommand():
            return disengage_command(state, command, regs)
        case HideCommand():
            return hide_command(state, command, regs, rng)
        case ShoveCommand():
            return shove_command(state, command, regs, rng)
        case JumpCommand():
            return jump_command(state, command, regs, rng)
        case ThrowCommand():
            return throw_command(state, command, regs, rng)
        case UseItemCommand():
            return use_item_command(state, command, regs, rng)
        case HelpCommand():
            return help_command(state, command, regs)
        case DodgeCommand():
            return dodge_command(state, command, regs)
        case EndTurnCommand():
            return _end_turn(state, command, rng)
        case FleeCommand():
            return flee_command(state, command, regs)
        case MonsterActionCommand():
            return monster_action_command(state, command, regs, rng)
        case FeatureActionCommand():
            return feature_action_command(state, command, regs, rng)
        case _:
            assert_never(command)


def execute_command(
    state: GameState, command: AnyCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    try:
        return _dispatch(state, command, regs, rng)
    except (EconomyRefused, EncounterRefused, ZoneError) as error:
        raise refusal_from(error) from None
