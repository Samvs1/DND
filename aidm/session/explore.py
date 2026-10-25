"""The exploration action queue and the free-text turn pipeline (SPEC 6.1, 6.2, 10).

Queue: FIFO, any seated player with a living hero may submit; at most ONE waiting entry per
player (the one being resolved does not count); everyone gets `queue_state` on every change;
one entry resolves at a time, never while paused, fighting or voting is irrelevant (a vote does
not block the queue). Combat free text from the active hero is a `creative_action`.

Resolution of one entry (`resolve_action`): the menu chooser first (look around ->
the manifest text; travel / short rest / long rest / shop -> a ready vote; inventory -> a
private listing; equip / unequip / drop -> `party_actions.item_intent`), else the adjudicator
with `apply` wired to THE reducer (dice and mechanical events are broadcast as they apply),
then `telling.conclude` (arrival, rewards, narration, NPC voice, memory, epilogue) and the
fight check. M22.1: the player's words are declared to the table first (`declared.declare`;
not for the private inventory listing), also for a creative action or a typed move in a fight.
A point-of-no-return result stores `PendingHostile` and asks only the acting player
(`pending_confirmation`); `confirm_hostile` re-runs the stored call with
`confirm_hostile=True` (no second model call), `cancel_hostile` drops it. A crossing that
leaves open tasks behind (M23.4, `move_party`) asks the same way, without the hold line. A
fight started by a weapon attack on an NPC rolls that attack before the narration
(`opening.strike_if_opening`, M19.2). Every entry ends in narration or a typed notice: never silent.
M23.8: a typed "what now" is answered before the queue (`what_now.answer`, not a turn), and a typed
move to a locked exit is told why it is shut (`BarredIntent`, `rules.gateway_lock`).
M27.5: typed gear use (`UseIntent`) runs through `gear_actions` (a refused use goes on to the
adjudicator); in a fight a typed put-out or light is `gear_actions.fight_gear`. M29.5b: a typed
feature or heal in a fight is the hotbar's command (`dm.fight_intent`). M30.0b: typed lines in
and out of a fight go through the one router (`dm.intent_router`).

M31.1a: the storyteller's turn, the held acts and their confirm / cancel are `session.held`; a
typed line in a fight is `session.fight_text`. M32.1a: one routed line (and the acts of a
compound line) is played by `session.intent_turn`; the votes it opens are `session.scene_votes`.
M36.12: typed lines are read by the menu chooser: a line out of a fight is
`session.menu_turn.menu_line`, a fight line `session.menu_fight_turn.menu_combat_line`, and
"what now" is the menu's own entry.

Public API: `acting_hero`, `submit_action`, `kick_resolver`, `resolve_next`, `resolve_action`.
"""

from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import (
    ErrorCode,
    NoticeKind,
    Resolving,
)
from aidm.models.protocol_views import QueueEntry, TablePhase
from aidm.models.state import Creature
from aidm.session import menu_fight_turn
from aidm.session.menu_turn import menu_line
from aidm.session.table_core import Player, TableCore


def acting_hero(core: TableCore, player: Player, text: str | None) -> Creature | None:
    """The hero who may act now, or None (the player was told why). `text` is the typed line
    (the router reads "what now" from it); a button's pick passes None (M36.11)."""
    if core.phase is not TablePhase.PLAY:
        ended = core.phase is TablePhase.ENDED
        words = "This tale has ended." if ended else "The adventure has not started yet."
        core.error(player.id, ErrorCode.WRONG_PHASE, words)
        return None
    pc = core.living_pc(player)
    if pc is None:
        core.error(player.id, ErrorCode.NO_CHARACTER, "You need a living hero to act.")
        return None
    if pc.hp <= 0:  # M11.1: a downed hero cannot act (v1: the unconscious hero kept typing)
        core.error(player.id, ErrorCode.NO_CHARACTER, "You are unconscious and cannot act.")
        return None
    if core.pending is not None and core.pending.player_id == player.id:
        core.pending = None  # a new action answers the open "Are you sure?" with no (M15.1)
    return pc


def submit_action(core: TableCore, player: Player, msg: SubmitAction) -> None:
    pc = acting_hero(core, player, msg.text)
    if pc is None:
        return
    if core.combat_active():
        menu_fight_turn.menu_combat_line(core, player, pc, msg.text)
        return
    if any(e.player_id == player.id for e in core.queue):
        core.error(player.id, ErrorCode.ALREADY_QUEUED, "Your next action is already waiting.")
        return
    core.queue.append(QueueEntry(player_id=player.id, creature_id=pc.id, text=msg.text))
    core.broadcast_queue()
    kick_resolver(core)


def kick_resolver(core: TableCore) -> None:
    idle = core.resolving is None and not core.resolver_scheduled
    ready = core.phase is TablePhase.PLAY and not core.paused and not core.in_combat
    if idle and ready and core.queue:
        core.resolver_scheduled = True
        core.schedule(lambda: resolve_next(core))


async def resolve_next(core: TableCore) -> None:
    core.resolver_scheduled = False
    if not core.queue or core.paused or core.in_combat:
        return
    entry = core.queue.popleft()
    core.resolving = entry
    core.broadcast(Resolving(entry=entry))
    core.broadcast_queue()
    try:
        await resolve_action(core, entry)
    finally:
        core.resolving = None
        core.broadcast_queue()


async def resolve_action(core: TableCore, entry: QueueEntry) -> None:
    player = core.players.get(entry.player_id)
    actor = core.state.creatures.get(entry.creature_id)
    if player is None or actor is None or actor.dead:
        core.notice(entry.player_id, NoticeKind.REFUSED, "Your hero can no longer act.")
        return
    await menu_line(core, player, actor, entry)  # M36.6: the menu's act, or the story
