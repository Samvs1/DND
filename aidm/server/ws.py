"""The WebSocket gateway `/ws` (SPEC 4, 10, DECISIONS M6.4).

One socket = one table connection: parse each text frame as a `ClientMsg` and `table.submit` it;
a pump task writes everything the table puts in `conn.outbox` to the socket. The first message
is `hello {name, token?, last_seq?}`; the table answers `welcome` + `snapshot` and re-sends the
missed `event` lines from `last_seq`. A bad frame (invalid JSON, unknown type, too large, binary)
gets a player-safe `error` message and the socket stays open; nothing here can crash it.

Public API: `serve_socket(socket, registry)`, `MAX_FRAME_CHARS`.
"""

import asyncio
import contextlib
import logging

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from aidm.models.protocol import client_adapter
from aidm.models.protocol_server import ErrorCode, ErrorMsg
from aidm.server.registry import TableRegistry
from aidm.session.table import Connection, Table

_LOG = logging.getLogger(__name__)
MAX_FRAME_CHARS = 65536
BAD_MESSAGE = "That message was not understood."
TOO_BIG = "That message is too large."


async def _pump(socket: WebSocket, conn: Connection) -> None:
    try:
        while True:
            msg = await conn.outbox.get()
            await socket.send_text(msg.model_dump_json())
    except (WebSocketDisconnect, RuntimeError):
        return


def _reject(table: Table, conn: Connection, text: str) -> None:
    table.send_conn(conn.id, ErrorMsg(code=ErrorCode.INVALID, text=text))


def _handle_frame(table: Table, conn: Connection, raw: str | bytes | None) -> None:
    if not isinstance(raw, str):
        _reject(table, conn, BAD_MESSAGE)
    elif len(raw) > MAX_FRAME_CHARS:
        _reject(table, conn, TOO_BIG)
    else:
        try:
            msg = client_adapter.validate_json(raw)
        except ValidationError:
            _reject(table, conn, BAD_MESSAGE)
        else:
            table.submit(conn.id, msg)


async def serve_socket(socket: WebSocket, registry: TableRegistry) -> None:
    await socket.accept()
    table = registry.table
    conn = table.connect()
    pump = asyncio.create_task(_pump(socket, conn))
    try:
        while True:
            frame = await socket.receive()
            if frame["type"] == "websocket.disconnect":
                break
            _handle_frame(table, conn, frame.get("text", frame.get("bytes")))
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        _LOG.exception("websocket handler failed")
    finally:
        pump.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump
        table.disconnect(conn.id)
