"""Spectator connections: the /screen view (SPEC 11, DECISIONS M8.3).

A `hello` with `spectator: true` registers the connection in `core.spectators`. It is NOT seated
(no player, no token, no `welcome`), receives every public broadcast plus the snapshot, the story
history and the missed event lines, and may only `ping`; anything else is refused.
`PublicState.screens` is the number of connected spectators, so players' narration audio defaults
to off while a screen plays it. A change of that count is broadcast as a fresh snapshot.

Public API: `join`, `leave`, `refuse`.
"""

from aidm.models.protocol_client import Hello
from aidm.models.protocol_server import ErrorCode, ErrorMsg
from aidm.session.table_core import TableCore

MAX_CATCH_UP = 500
WATCH_ONLY = "The screen only watches."


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
