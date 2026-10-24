"""Typed lines of the active hero in a fight (split out of `session.explore` in M31.1a; SPEC 6.1).

`combat_text(core, player, pc, text)`: a typed put-out or light is `gear_actions.fight_gear`
(M27.5); otherwise on the hero's own turn the one router's fight rows (`dm.intent_router`) read
the line first: a move is the Move list's commands (M19.4), a surrender demand one engine check
(M29.9a T12), and a weapon attack, a feature, a healing draught or (M31.1a V1) a cast of a ready
spell or a targeted feature is the hotbar's own command, so the rules charge or refuse it with
their reason. A cast line that cannot name a valid target is refused plainly (`RefusedIntent`,
nothing spent, never a creative check). Anything else is a creative action: the storyteller's
call, which spends the action.

Public API: `combat_text`.
"""

from aidm.dm.attack_intent import DrawAttack
from aidm.dm.fight_cast_intent import RefusedIntent
from aidm.dm.fight_intent import FightCommand
from aidm.dm.intent_router import fight_intent
from aidm.dm.surrender_intent import SurrenderIntent
from aidm.models.commands import DashCommand, MoveCommand
from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.models.state import Creature
from aidm.rules.turns import EconomyRefused, spend_action
from aidm.session import combat_flow, gear_actions
from aidm.session.declared import declare
from aidm.session.held import adjudicated
from aidm.session.surrender_turn import ACTION_SPENT, surrender_turn
from aidm.session.table_core import Player, TableCore

NOT_YOUR_TURN = "It is not your turn."


def _my_turn(core: TableCore, creature_id: str) -> bool:
    enc = core.state.encounter
    return enc is not None and enc.active_id() == creature_id and core.turn_key is not None


def combat_text(core: TableCore, player: Player, pc: Creature, text: str) -> None:
    entry = QueueEntry(player_id=player.id, creature_id=pc.id, text=text)
    if gear_actions.fight_gear(core, player, entry):  # M27.5: put out (free) or light (bonus)
        return
    if not _my_turn(core, pc.id):
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, NOT_YOUR_TURN)
        return
    found = fight_intent(core.state, pc.id, text)  # M30.0b: the one router's fight rows
    if isinstance(found, RefusedIntent):  # M31.1a V1: a cast with no valid target, nothing spent
        core.notice(player.id, NoticeKind.REFUSED, found.text)
        return
    if isinstance(found, list):  # M19.4: "I move to the ravine" moves (no action spent)
        moves = found
        core.schedule(lambda: _typed_move(core, player, entry, moves))
        return
    if isinstance(found, SurrenderIntent):  # M29.9a T12: one engine check, not a story roll
        demand = found
        core.schedule(lambda: surrender_turn(core, player, entry, demand))
        return
    if found is not None:  # M29.5b / M31.1a: the hotbar's command, typed
        command = found
        core.schedule(lambda: _typed_command(core, player, entry, command))
        return
    if not _action_left(core, pc.id):
        core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
        return
    core.schedule(lambda: _creative(core, player, entry))


async def _creative(core: TableCore, player: Player, entry: QueueEntry) -> None:
    if not _my_turn(core, entry.creature_id):
        core.error(player.id, ErrorCode.NOT_YOUR_TURN, NOT_YOUR_TURN)
        return
    if not _action_left(core, entry.creature_id):
        core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
        return
    await combat_flow.tell_segment(core)
    declare(core, entry)
    result = await adjudicated(core, entry, creative=True)
    if result.spends_action:  # M30.1: an impossible verdict alone is free
        _spend_action(core, entry.creature_id)
    core.segment = []
    await combat_flow.after_player_step(core, entry.creature_id)


async def _typed_command(
    core: TableCore, player: Player, entry: QueueEntry, command: FightCommand | DrawAttack
) -> None:
    """A typed feature, cast or heal runs as the hotbar command (a refusal says the rules'
    reason)."""
    declare(core, entry)
    if isinstance(command, DrawAttack):  # M30.0b T9: the free draw of a stowed weapon first
        if not gear_actions.draw_weapon(core, player, command):
            return
        command = command.attack
    await combat_flow.player_command(core, player, command)


async def _typed_move(
    core: TableCore, player: Player, entry: QueueEntry, moves: list[MoveCommand | DashCommand]
) -> None:
    """The commands the phone's Move list sends; a refusal is answered the same way."""
    creature_id = entry.creature_id
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
