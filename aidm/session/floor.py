"""Who is typing (M11.2): the public "Sam is typing..." line of the shared screen.

A seated player's controller sends `typing {on}` while composing. `on: true` starts (or refreshes)
the player's typing mark and an expiry timer (`TYPING_SECONDS`); a new mark, a stop and an expiry
each broadcast `floor_state` (holder, queue, typing; `TableCore.floor_view`). Refreshes are
quiet. Messages over the rate limit are dropped without an error (typing is cosmetic), and so is
typing outside the PLAY phase. Submitting an action, leaving the table, the defeat and a campaign
switch clear the mark. Nothing here is an event or persisted.

Public API: `TYPING_SECONDS`, `typing`, `stop_typing`, `typing_expired`, `clear_typing`.
"""

from aidm.models.protocol_client import Typing
from aidm.models.protocol_views import TablePhase
from aidm.session.table_core import Player, TableCore

TYPING_SECONDS = 8.0


def typing(core: TableCore, player: Player, msg: Typing) -> None:
    if core.phase is not TablePhase.PLAY:
        return
    if not core.typing_limit.allow(player.id, core.config.clock.time()):
        return
    if not msg.on:
        stop_typing(core, player.id)
        return
    gen, fresh = core.typing.start(player.id)
    timer = core.start_timer("typing", f"{player.id}:{gen}", TYPING_SECONDS)
    core.typing.keep_timer(player.id, timer)
    if fresh:
        core.broadcast_floor()


def stop_typing(core: TableCore, player_id: str) -> None:
    if core.typing.stop(player_id):
        core.broadcast_floor()


def typing_expired(core: TableCore, key: str) -> None:
    player_id, _, gen = key.rpartition(":")
    if gen.isdigit() and core.typing.expire(player_id, int(gen)):
        core.broadcast_floor()


def clear_typing(core: TableCore) -> None:
    """Drop every typing mark (the caller broadcasts the floor or a snapshot)."""
    core.typing.clear()
