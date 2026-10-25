"""Playing one act of a typed line in a fight (split out of `session.explore` in M31.1a; SPEC 6.1).

`play_act` plays one act of the menu interpreter (`session.menu_fight_turn`): a move list (M19.4),
a hotbar command, a draw, a surrender demand (one engine check, M29.9a T12), a refusal, an
impossible feat (M32.1a X8: no dice, no action spent), or None: the creative action, the
storyteller's call, which spends the action. `my_turn` checks the hero's turn.

Public API: `NOT_YOUR_TURN`, `play_act`, `my_turn`.
"""

from aidm.dm.narration_templates import template_line
from aidm.models.commands import DashCommand, MoveCommand
from aidm.models.impossible import ActionImpossible
from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.rules.acts import ImpossibleIntent, RefusedIntent
from aidm.rules.acts_fight import DrawAttack, FightCommand, FightIntent, SurrenderIntent
from aidm.rules.turns import EconomyRefused, spend_action
from aidm.session import combat_flow, gear_actions
from aidm.session.declared import declare
from aidm.session.held import adjudicated
from aidm.session.surrender_turn import ACTION_SPENT, surrender_turn
from aidm.session.table_core import Player, TableCore
from aidm.session.telling import remember, tell_text

NOT_YOUR_TURN = "It is not your turn."


def my_turn(core: TableCore, creature_id: str) -> bool:
    enc = core.state.encounter
    return enc is not None and enc.active_id() == creature_id and core.turn_key is not None


async def play_act(
    core: TableCore, player: Player, entry: QueueEntry, found: FightIntent | None, say: bool = True
) -> None:
    if found is None:
        await _creative(core, player, entry, say)
    elif isinstance(found, RefusedIntent):
        core.notice(player.id, NoticeKind.REFUSED, found.text)
    elif isinstance(found, list):  # M19.4: "I move to the ravine" moves (no action spent)
        await _typed_move(core, player, entry, found, say)
    elif isinstance(found, SurrenderIntent):  # M29.9a T12: one engine check, not a story roll
        await surrender_turn(core, player, entry, found, say=say)
    elif isinstance(found, ImpossibleIntent):  # M32.1a X8: no dice, no action spent
        await _impossible(core, entry, found, say)
    else:  # M29.5b / M31.1a: the hotbar's command, typed
        await _typed_command(core, player, entry, found, say)


async def _creative(core: TableCore, player: Player, entry: QueueEntry, say: bool) -> None:
    if not my_turn(core, entry.creature_id):
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, NOT_YOUR_TURN)
        return
    if not _action_left(core, entry.creature_id):
        core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
        return
    await combat_flow.tell_segment(core)
    if say:
        declare(core, entry)
    result = await adjudicated(core, entry, creative=True)
    if result.spends_action:  # M30.1: an impossible verdict alone is free
        _spend_action(core, entry.creature_id)
    core.segment = []
    await combat_flow.after_player_step(core, entry.creature_id)


async def _impossible(
    core: TableCore, entry: QueueEntry, intent: ImpossibleIntent, say: bool
) -> None:
    await combat_flow.tell_segment(core)
    if say:
        declare(core, entry)
    event = ActionImpossible(creature_id=intent.actor_id, text=intent.text, reason=intent.reason)
    applied = core.apply_all([event])
    core.segment = []
    line = template_line(core.state, event) or intent.reason
    await remember(core, await tell_text(core, line), applied)


async def _typed_command(
    core: TableCore,
    player: Player,
    entry: QueueEntry,
    command: FightCommand | DrawAttack,
    say: bool,
) -> None:
    """A typed feature, cast or heal runs as the hotbar command (a refusal says the rules'
    reason)."""
    if say:
        declare(core, entry)
    if isinstance(command, DrawAttack):  # M30.0b T9: the free draw of a stowed weapon first
        if not gear_actions.draw_weapon(core, player, command):
            return
        command = command.attack
    await combat_flow.player_command(core, player, command)


async def _typed_move(
    core: TableCore,
    player: Player,
    entry: QueueEntry,
    moves: list[MoveCommand | DashCommand],
    say: bool,
) -> None:
    """The commands the phone's Move list sends; a refusal is answered the same way."""
    creature_id = entry.creature_id
    if say:
        declare(core, entry)
    for command in moves:
        await combat_flow.player_command(core, player, command)
    goal = next((m.zone_id for m in moves if isinstance(m, MoveCommand)), None)
    enc = core.state.encounter
    here = enc.combatants.get(creature_id) if enc is not None else None
    if enc is not None and here is not None and here.zone_id == goal:
        zone = next(z.name for z in enc.zone_map.zones if z.id == goal)
        core.notice(player.id, NoticeKind.INFO, f"You move to {zone}.")


def _action_left(core: TableCore, creature_id: str) -> bool:
    """A creative action costs the hero's action (SPEC 6.1; DECISIONS M9.5 QA-01)."""
    enc = core.state.encounter
    combatant = enc.combatants.get(creature_id) if enc is not None else None
    return combatant is not None and combatant.economy.action


def _spend_action(core: TableCore, creature_id: str) -> None:
    try:
        core.apply_all(spend_action(core.state, creature_id, reason="creative action"))
    except EconomyRefused:
        return  # the effect ended the fight or the hero's turn: nothing left to spend
