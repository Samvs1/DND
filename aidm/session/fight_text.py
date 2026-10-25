"""Typed lines of the active hero in a fight (split out of `session.explore` in M31.1a; SPEC 6.1).

`combat_text(core, player, pc, text)`: a typed put-out or light is `gear_actions.fight_gear`
(M27.5); otherwise on the hero's own turn the one router's fight rows (`dm.intent_router`) read
the line first: a move is the Move list's commands (M19.4), a surrender demand one engine check
(M29.9a T12), and a weapon attack, a feature, a healing draught or (M31.1a V1) a cast of a ready
spell or a targeted feature is the hotbar's own command, so the rules charge or refuse it with
their reason. A cast line that cannot name a valid target is refused plainly (`RefusedIntent`,
nothing spent, never a creative check). M32.1a X8: a feat no body could do is the engine's
`ActionImpossible` (no dice, no action spent). Anything else is a creative action: the
storyteller's call, which spends the action.

M32.1a X6 (round 5: "I charge the zombie and cleave it with my longsword" only moved): a compound
line (`dm.compound_lines`) whose acts each route is every act in order (the move, then the
attack); a move followed by words no row reads is the move, then those words as the creative
action. The whole line is declared once; the acts stop when the turn or the fight ends.

Public API: `combat_text`.
"""

from aidm.dm.compound_lines import clause_parts, is_lead_in
from aidm.dm.intent_router import fight_intent
from aidm.dm.narration_templates import template_line
from aidm.models.commands import DashCommand, MoveCommand
from aidm.models.impossible import ActionImpossible
from aidm.models.protocol_server import ErrorCode, NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.models.state import Creature, GameState
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
type _Act = tuple[str, FightIntent | None]


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
    plan = _plan(core.state, pc.id, text, found)
    if plan:  # M32.1a X6: every act of a compound line
        core.schedule(lambda: _play_plan(core, player, entry, plan))
        return
    if isinstance(found, RefusedIntent):  # M31.1a V1: a cast with no valid target, nothing spent
        core.notice(player.id, NoticeKind.REFUSED, found.text)
        return
    if found is None and not _action_left(core, pc.id):
        core.error(player.id, ErrorCode.REFUSED, ACTION_SPENT)
        return
    core.schedule(lambda: _play(core, player, entry, found))


def _plan(state: GameState, actor_id: str, text: str, whole: FightIntent | None) -> list[_Act]:
    parts = clause_parts(state, actor_id, text)
    if len(parts) < 2:
        return []
    routed = [fight_intent(state, actor_id, part) for part in parts]
    acts: list[_Act] = []
    if isinstance(whole, list) and not any(isinstance(r, list) for r in routed):
        acts.append((text, whole))  # the move the whole line reads ("vault up ... at the thug")
    for part, act in zip(parts, routed, strict=True):
        if act is not None and all(act != done for _, done in acts):  # one act said twice: once
            acts.append((part, act))
    if len(acts) >= 2:
        return acts
    if isinstance(whole, list) and len(acts) == 1:  # a move, then words no row reads
        unread = [p for p, r in zip(parts, routed, strict=True) if r is None]
        said = [p for p in unread if not is_lead_in(p)]  # M33.1: a gesture goes with the rest
        return [*acts, (" and ".join(unread), None)] if said else []
    return []


async def _play_plan(core: TableCore, player: Player, entry: QueueEntry, plan: list[_Act]) -> None:
    await combat_flow.tell_segment(core)
    declare(core, entry)
    for part, act in plan:
        if not _my_turn(core, entry.creature_id):
            return
        await _play(core, player, entry.model_copy(update={"text": part}), act, say=False)


async def _play(
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
    if not _my_turn(core, entry.creature_id):
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
