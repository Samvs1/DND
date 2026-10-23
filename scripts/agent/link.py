"""One short-lived websocket for one hero: connect with its token, act, wait, disconnect.

The background server keeps the game; every CLI command reconnects as a seated player (the
token from `session.json`), sends its message and waits until the table is quiet again: no turn
resolving and no new message for a moment. Everything the server said meanwhile is returned so
the CLI can print a short digest.

Public API: `Link`, `open_link`.
"""

import asyncio
import time
from typing import Any

from scripts.agent.session import Session
from scripts.sim.client import Conn

Msg = dict[str, Any]
QUIET_FAKE_S = 0.8
QUIET_LIVE_S = 2.0
FAKE_WAIT_S = 90.0
LIVE_WAIT_S = 300.0


class Link:
    def __init__(self, session: Session, name: str) -> None:
        self.session = session
        self.conn = Conn(name, session.url)
        self.quiet = QUIET_LIVE_S if session.live else QUIET_FAKE_S
        self.wait = LIVE_WAIT_S if session.live else FAKE_WAIT_S

    async def open(self, token: str | None = None) -> None:
        await self.conn.open()
        await self.conn.send({"type": "hello", "name": self.conn.name, "token": token})
        welcome = await self.conn.wait_for(lambda m: m["type"] == "welcome", 20.0)
        self.conn.player_id = welcome["player_id"]
        self.conn.token = welcome["token"]
        self.conn.is_host = bool(welcome.get("is_host"))
        await self.conn.wait_for(lambda m: m["type"] == "snapshot", 20.0)

    async def close(self) -> None:
        await self.conn.close()

    @property
    def state(self) -> Msg:
        return self.conn.state

    @property
    def seq(self) -> int:
        """The newest event number this link has seen (snapshot or event stream)."""
        seqs = [m["seq"] for m in self.conn.log if m["type"] in ("snapshot", "event")]
        return max(seqs, default=0)

    def _busy(self) -> bool:
        queue = next((m for m in reversed(self.conn.log) if m["type"] == "queue_state"), None)
        if queue is not None and queue.get("resolving") is not None:
            return True
        return bool(self.state.get("resolving"))

    async def settle(self, mark: int) -> list[Msg]:
        """Wait until nothing is resolving and the log stopped growing; return the new messages."""
        deadline = time.monotonic() + self.wait
        last, changed = len(self.conn.log), time.monotonic()
        while time.monotonic() < deadline and not self.conn.closed:
            await asyncio.sleep(0.15)
            if len(self.conn.log) != last:
                last, changed = len(self.conn.log), time.monotonic()
            if not self._busy() and time.monotonic() - changed >= self.quiet:
                break
        return self.conn.log[mark:]

    async def send(self, msg: Msg) -> list[Msg]:
        """Send one message, wait for the table to settle, return what the server said."""
        mark = self.conn.mark()
        await self.conn.send(msg)
        await asyncio.sleep(0.4)  # let a queued turn show as resolving before we test for idle
        return await self.settle(mark)

    async def sheet(self) -> Msg | None:
        mark = self.conn.mark()
        await self.conn.send({"type": "request_sheet"})
        try:
            got = await self.conn.wait_for(lambda m: m["type"] in ("sheet", "error"), 10.0, mark)
        except TimeoutError:
            return None
        return got["sheet"] if got["type"] == "sheet" else None

    async def best_option(self, target_id: str) -> str:
        """The strike with the best hit chance in range (what the Strike button would pick)."""
        mark = self.conn.mark()
        await self.conn.send({"type": "request_hit_chances", "target_id": target_id})

        def done(m: Msg) -> bool:
            return m["type"] == "error" or (
                m["type"] == "hit_chances" and m["target_id"] == target_id
            )

        try:
            got = await self.conn.wait_for(done, 10.0, mark)
        except TimeoutError:
            return "main_hand"
        weapons = [c for c in got.get("chances", []) if not str(c["option"]).startswith("spell:")]
        usable = [c for c in weapons if c.get("in_range", True)]
        pool = usable or weapons
        return str(max(pool, key=lambda c: c["probability"])["option"]) if pool else "main_hand"

    async def command(self, cmd: Msg) -> list[Msg]:
        if cmd["type"] == "attack" and not cmd.get("option"):
            cmd = {**cmd, "option": await self.best_option(cmd["target_id"])}
        return await self.send({"type": "combat_command", "command": cmd})


async def open_link(session: Session, player: Msg) -> Link:
    link = Link(session, player["name"])
    await link.open(player.get("token"))
    return link
