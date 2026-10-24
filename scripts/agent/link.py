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

from scripts.agent.damage import pick_option
from scripts.agent.session import Session
from scripts.sim.client import Conn

Msg = dict[str, Any]
QUIET_FAKE_S = 0.8
QUIET_LIVE_S = 2.0
GRACE_FAKE_S = 1.5
GRACE_LIVE_S = 15.0
FAKE_WAIT_S = 90.0
LIVE_WAIT_S = 300.0


class Link:
    def __init__(self, session: Session, name: str) -> None:
        self.session = session
        self.conn = Conn(name, session.url)
        self.quiet = QUIET_LIVE_S if session.live else QUIET_FAKE_S
        self.wait = LIVE_WAIT_S if session.live else FAKE_WAIT_S
        self.grace = GRACE_LIVE_S if session.live else GRACE_FAKE_S

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
        return bool(self.state.get("resolving")) or self._foe_turn()

    def _foe_turn(self) -> bool:
        """A foe's turn is running: its narration is still to come (M31.1e: an `act` in a fight
        returned in the pause between the hero's line and the foes' turns, so the footer lagged)."""
        combat = self.state.get("combat") or {}
        active = next(
            (t for t in combat.get("tokens", []) if t["creature_id"] == combat.get("active_id")),
            None,
        )
        return bool(active) and active["side"] not in ("party", "neutral") and not active["dead"]

    def _told(self, mark: int) -> bool:
        """The narration for the acted turn arrived (or nothing was acted, so none is due)."""
        new = self.conn.log[mark:]
        if not any(m["type"] in ("event", "dice_roll") for m in new):
            return True
        return any(m["type"] in ("narration_done", "epilogue", "error") for m in new)

    async def settle(self, mark: int) -> list[Msg]:
        """Wait until nothing is resolving, the log stopped growing and the acted turn's narration
        arrived (M29.7e H12: the live model is silent for a while after the result); a bounded
        quiet period after the last message ends the wait when no narration is coming."""
        deadline = time.monotonic() + self.wait
        last, changed = len(self.conn.log), time.monotonic()
        while time.monotonic() < deadline and not self.conn.closed:
            await asyncio.sleep(0.15)
            if len(self.conn.log) != last:
                last, changed = len(self.conn.log), time.monotonic()
            idle = time.monotonic() - changed
            told = self._told(mark) or idle >= self.grace
            if not self._busy() and idle >= self.quiet and told:
                break
        return self.conn.log[mark:]

    async def send(self, msg: Msg) -> list[Msg]:
        """Send one message, wait for the table to settle, return what the server said."""
        mark = self.conn.mark()
        await self.conn.send(msg)
        await asyncio.sleep(0.4)  # let a queued turn show as resolving before we test for idle
        return await self.settle(mark)

    async def what_now(self) -> list[Msg]:
        """Ask What now? (the engine's next-step lines; a read-only reply, not a turn)."""
        mark = self.conn.mark()
        await self.conn.send({"type": "what_now"})
        try:
            await self.conn.wait_for(
                lambda m: m["type"] in ("what_now_answer", "error"), 10.0, mark
            )
        except TimeoutError:
            return []
        return self.conn.log[mark:]

    def last_roll(self) -> Msg | None:
        """The newest dice roll this link heard (live, or the recent ones sent on connect)."""
        for m in reversed(self.conn.log):
            if m["type"] == "dice_roll":
                return m["dice"]
            if m["type"] == "story_history" and m.get("dice"):
                return m["dice"][-1]["dice"]
        return None

    async def sheet(self) -> Msg | None:
        got = await self.sheet_msg()
        return got["sheet"] if got else None

    async def sheet_msg(self) -> Msg | None:
        mark = self.conn.mark()
        await self.conn.send({"type": "request_sheet"})
        try:
            got = await self.conn.wait_for(lambda m: m["type"] in ("sheet", "error"), 10.0, mark)
        except TimeoutError:
            return None
        return got if got["type"] == "sheet" else None

    async def best_option(self, target_id: str) -> str:
        """The strike with the best expected damage in range (M29.7e H8: hit chance x damage)."""
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
        sheet = await self.sheet()
        attacks = list((sheet or {}).get("attacks", []))
        return pick_option(list(got.get("chances", [])), attacks)

    async def command(self, cmd: Msg) -> list[Msg]:
        if cmd["type"] == "attack" and not cmd.get("option"):
            cmd = {**cmd, "option": await self.best_option(cmd["target_id"])}
        return await self.send({"type": "combat_command", "command": cmd})


async def open_link(session: Session, player: Msg) -> Link:
    link = Link(session, player["name"])
    await link.open(player.get("token"))
    return link
