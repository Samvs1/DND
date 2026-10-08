"""Spectator connections: the /screen view (SPEC 11, DECISIONS M8.3).

A `hello` with `role: "screen"` (or the older `spectator: true`; `wants_screen`) registers the
connection in `core.spectators`. It is NOT seated (no player, no token, no `welcome`), receives
every public broadcast plus the snapshot, the story history and the missed event lines, and may
only `ping`; anything else is refused.
`PublicState.screens` is the number of connected spectators, so players' narration audio defaults
to off while a screen plays it. A change of that count is broadcast as a fresh snapshot.

It never receives a message addressed to one player (`TableCore.send`: sheets, level-up offers,
private notices, hit chances, exports), only `TableCore.broadcast`s and its own snapshot/history;
tests/session/test_screen_privacy.py proves it (M11.2).

Public API: `wants_screen`, `join`, `leave`, `refuse`.
"""

from typing import TypeGuard

from aidm.models.protocol import AnyClientMsg
from aidm.models.protocol_client import DeviceRole, Hello
from aidm.models.protocol_server import ErrorCode, ErrorMsg
from aidm.session.table_core import TableCore

MAX_CATCH_UP = 500
WATCH_ONLY = "The screen only watches."


def wants_screen(msg: AnyClientMsg) -> TypeGuard[Hello]:
    """A hello from the shared display (M11.2 role "screen", or the M8.3 `spectator` flag)."""
    return isinstance(msg, Hello) and (msg.spectator or msg.role is DeviceRole.SCREEN)


def join(core: TableCore, conn_id: str, msg: Hello) -> None:
    core.spectators.add(conn_id)
    core.broadcast_snapshot()  # the new screen's first message, and the new count for players
    core.send_conn(conn_id, core.public.history())
    if msg.last_seq is not None:
        for line in core.public.since(msg.last_seq, MAX_CATCH_UP):
            core.send_conn(conn_id, line)


def leave(core: TableCore, conn_id: str) -> bool:
    """Drop a spectator connection; False when `conn_id` was not one."""
    if conn_id not in core.spectators:
        return False
    core.spectators.discard(conn_id)
    core.outboxes.pop(conn_id, None)
    core.broadcast_snapshot()
    return True


def refuse(core: TableCore, conn_id: str) -> None:
    core.send_conn(conn_id, ErrorMsg(code=ErrorCode.REFUSED, text=WATCH_ONLY))
