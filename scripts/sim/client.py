"""A bot's real websocket connection: sends frames, records every server message.

`Conn` keeps the full message log and the newest snapshot state so the bots and the director can
wait for conditions with `wait_for` (a predicate over the log from a position onward). Like the
browser (`handlers.js` onCombat), a `combat_state` patches the state's `combat` at once: since
M20.3 a hero's `turn_prompt` follows its `combat_state` before the next snapshot.

Public API: `Conn`, `Msg`.
"""

import asyncio
import contextlib
import json
import time
from collections.abc import Callable
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

type Msg = dict[str, Any]


class Conn:
    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url
        self.log: list[Msg] = []
        self.player_id = ""
        self.token = ""
        self.is_host = False
        self.state: Msg = {}
        self.closed = False
        self._ws: ClientConnection | None = None
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()

    async def open(self) -> None:
        self._ws = await websockets.connect(self.url, max_size=None, open_timeout=20)
        self._task = asyncio.create_task(self._read())

    async def hello(self, timeout: float = 20.0) -> None:
        await self.send({"type": "hello", "name": self.name})
        welcome = await self.wait_for(lambda m: m["type"] == "welcome", timeout)
        self.player_id = welcome["player_id"]
        self.token = welcome["token"]
        self.is_host = bool(welcome.get("is_host"))

    async def _read(self) -> None:
        try:
            assert self._ws is not None
            async for raw in self._ws:
                msg: Msg = json.loads(raw)
                if msg.get("type") == "snapshot":
                    self.state = msg["state"]
                elif msg.get("type") == "combat_state" and self.state:
                    self.state = {**self.state, "combat": msg.get("combat")}
                self.log.append(msg)
                self._wake.set()
        except websockets.ConnectionClosed:
            pass
        finally:
            self.closed = True
            self._wake.set()

    async def send(self, obj: Msg) -> None:
        await self.send_raw(json.dumps(obj))

    async def send_raw(self, text: str | bytes) -> None:
        assert self._ws is not None
        await self._ws.send(text)

    async def wait_idx(self, pred: Callable[[Msg], bool], timeout: float, since: int = 0) -> int:
        """Log position of the first message at position >= `since` matching `pred`."""
        deadline = time.monotonic() + timeout
        seen = since
        while True:
            while seen < len(self.log):
                seen += 1
                if pred(self.log[seen - 1]):
                    return seen - 1
            left = deadline - time.monotonic()
            if left <= 0 or self.closed:
                raise TimeoutError(f"{self.name}: no matching message in {timeout:.0f}s")
            self._wake.clear()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), min(left, 1.0))

    async def wait_for(self, pred: Callable[[Msg], bool], timeout: float, since: int = 0) -> Msg:
        """The first message at position >= `since` matching `pred` (else TimeoutError)."""
        return self.log[await self.wait_idx(pred, timeout, since)]

    def mark(self) -> int:
        return len(self.log)

    def of_type(self, kind: str, since: int = 0) -> list[Msg]:
        return [m for m in self.log[since:] if m["type"] == kind]

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
        if self._task is not None:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
