"""A bot player: one real websocket, one hero, a seeded RNG.

`Bot` wraps `Conn` with the protocol moves the director and the roles use: create the hero,
submit a tracked action (silent turns are failures), answer votes, play combat turns from the
`turn_prompt`, level up. Behaviour that differs per role lives in `explore.py` and `chaos.py`.

Public API: `Bot`, `TERMINAL`.
"""

import asyncio
import random
from typing import Any

from scripts.sim.client import Conn, Msg
from scripts.sim.combat import MAX_STEPS, Plan, choose_command, foes_of, pick_target
from scripts.sim.report import Report

# What a player sees as "my action was handled".
TERMINAL = frozenset(
    {
        "narration_done",
        "notice",
        "vote_open",
        "pending_confirmation",
        "encounter_offer",
        "error",
        "epilogue",
    }
)


PLAN_ROLE = {"fighter": "fighter", "explorer": "caster", "chaos": "rogue"}


def _idle(m: Msg) -> bool:
    return m["type"] == "queue_state" and m.get("resolving") is None


class Bot:
    def __init__(
        self, conn: Conn, role: str, class_index: str, rng: random.Random, report: Report
    ) -> None:
        self.conn = conn
        self.role = role
        self.class_index = class_index
        self.rng = rng
        self.report = report
        self.plan = Plan(role=PLAN_ROLE[role], hero_id="", rng=rng)
        self.turn_task: asyncio.Task[None] | None = None
        self.answered_prompts = 0
        # Scales the short per-command waits (combat, sheet): 1.0 fake AI, more with --live-ai.
        self.patience = 1.0

    @property
    def name(self) -> str:
        return self.conn.name

    @property
    def hero_id(self) -> str:
        return f"pc-{self.conn.player_id}"

    async def create_hero(self, choices: Msg, timeout: float = 15.0) -> Msg:
        mark = self.conn.mark()
        await self.conn.send({"type": "create_character", "choices": choices})
        result = await self.conn.wait_for(lambda m: m["type"] == "creation_result", timeout, mark)
        self.plan.hero_id = self.hero_id
        cantrips = choices.get("cantrips") or []
        self.plan.cantrip = cantrips[0] if cantrips and self.plan.role == "caster" else None
        return result

    def me(self) -> Msg | None:
        party = self.conn.state.get("party", [])
        return next((c for c in party if c["id"] == self.hero_id), None)

    # --- tracked actions ---------------------------------------------------------------

    async def submit(self, text: str, timeout: float = 60.0) -> str:
        """Send `submit_action` and wait until it is resolved; returns the outcome label.

        Resolved = a typed `error`, or my entry went `resolving` and, before the queue went
        idle again, I saw a narration / notice / vote / offer. Nothing within `timeout` (or a
        resolution with none of those) is a silent turn and fails the seed.
        """
        conn, mark = self.conn, self.conn.mark()
        self.report.submits += 1
        await conn.send({"type": "submit_action", "text": text})
        mine = self._mine(text)
        try:
            start = await conn.wait_idx(mine, timeout, mark)
        except TimeoutError:
            return self._silent(text, "no resolving, error or notice")
        first = conn.log[start]
        if first["type"] != "resolving":
            return f"{first['type']}:{first.get('code', first.get('kind', ''))}"
        try:
            await conn.wait_idx(_idle, timeout, start)
        except TimeoutError:
            return self._silent(text, "resolving never finished")
        window = conn.log[start:]
        if not any(m["type"] in TERMINAL for m in window):
            return self._silent(text, "resolved with no narration, notice or vote")
        self.report.turns += 1
        return "resolved"

    def _mine(self, text: str) -> Any:
        pid = self.conn.player_id

        def match(m: Msg) -> bool:
            if m["type"] == "error":
                return True
            if m["type"] == "notice" and "overtakes your plan" in m.get("text", ""):
                return True
            entry = m.get("entry") or {}
            return m["type"] == "resolving" and entry.get("player_id") == pid

        return match

    def _my_prompt(self, m: Msg) -> bool:
        return m["type"] == "turn_prompt" and m["creature_id"] == self.hero_id

    def _silent(self, text: str, why: str) -> str:
        self.report.fail(f"SILENT TURN {self.name} {text[:60]!r}: {why}")
        return "silent"

    async def vote(self, vote_id: str, ready: bool) -> None:
        await self.conn.send({"type": "vote", "vote_id": vote_id, "ready": ready})

    # --- combat ------------------------------------------------------------------------

    async def _command(self, cmd: Msg, timeout: float = 20.0) -> str:
        timeout *= self.patience
        mark = self.conn.mark()
        await self.conn.send({"type": "combat_command", "command": cmd})
        got = await self.conn.wait_for(lambda m: m["type"] in ("error", "snapshot"), timeout, mark)
        self.report.turns += 1
        return f"refused:{got.get('refusal') or got['code']}" if got["type"] == "error" else "ok"

    async def _chances(self, target_id: str, timeout: float = 10.0) -> list[Msg]:
        timeout *= self.patience
        mark = self.conn.mark()
        await self.conn.send({"type": "request_hit_chances", "target_id": target_id})

        def answer(m: Msg) -> bool:
            return m["type"] == "error" or (
                m["type"] == "hit_chances" and m["target_id"] == target_id
            )

        got = await self.conn.wait_for(answer, timeout, mark)
        return [] if got["type"] == "error" else list(got["chances"])

    async def play_turn(self) -> None:
        """One hero turn: up to MAX_STEPS safe commands, then end_turn."""
        self.plan.refused = set()
        for _ in range(MAX_STEPS):
            combat = self.conn.state.get("combat")
            if not combat or combat["active_id"] != self.hero_id:
                return
            foes = foes_of(combat, self.hero_id)
            if not foes:
                return
            target = pick_target(self.plan, combat, foes)
            chances = await self._chances(target["creature_id"])
            cmd = choose_command(self.plan, combat, chances, target)
            outcome = await self._command(cmd)
            self.report.say(f"{self.name} {cmd['type']} {cmd.get('target_id', '')} -> {outcome}")
            if outcome.startswith("refused"):
                self.plan.refused.add(cmd["type"])
            if cmd["type"] == "end_turn":
                return
        await self._command({"type": "end_turn", "actor_id": self.hero_id})

    async def fight(self, stop: asyncio.Event) -> None:
        """Answer every `turn_prompt` for my hero until `stop` is set (a background task)."""
        index = 0
        while not stop.is_set() and not self.conn.closed:
            try:
                index = await self.conn.wait_idx(self._my_prompt, 1.0, index) + 1
            except TimeoutError:
                continue
            self.answered_prompts += 1
            await self.play_turn()
