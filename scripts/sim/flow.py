"""The director: plays one campaign through its phases with the three bots.

Phases: start the campaign, chaos probes, exploration rounds (all three act at once, so the
queue is exercised), travel by ready vote, the encounter offer and a FULL combat (each bot
answers its own `turn_prompt`), a short rest, a level-up and the walk to the region gateway.

Public API: `Director`.
"""

import asyncio
import random

from scripts.sim.bot import Bot
from scripts.sim.chaos import run_probes
from scripts.sim.checks import engine_invariants
from scripts.sim.client import Msg
from scripts.sim.explore import explore_text, scene_of
from scripts.sim.levelup import level_up_bot
from scripts.sim.report import Report
from scripts.sim.server import SimServer
from scripts.sim.setup import Party

VOTE_ATTEMPTS = 3


class Director:
    def __init__(
        self, srv: SimServer, party: Party, report: Report, timeout: float, seed: int
    ) -> None:
        self.srv, self.party, self.report, self.timeout = srv, party, report, timeout
        self.rng = random.Random(seed)
        self.hub = ""
        self.fights = 0
        self.short_rests = 0
        self.long_rests = 0

    @property
    def host(self) -> Bot:
        return self.party.fighter

    def state(self) -> Msg:
        return self.host.conn.state

    async def settle(self) -> None:
        """Wait until the table has no work left and the sockets had time to deliver."""
        await self.srv.table.settle()
        await asyncio.sleep(0.25)
        self.invariants()

    def invariants(self) -> None:
        for problem in engine_invariants(self.srv.table.state):
            self.report.fail(f"engine invariant: {problem}")

    def at_hub(self) -> bool:
        return scene_of(self.state()).get("node_id") == self.hub

    def party_line(self) -> str:
        """hp / xp / state of every hero plus the active combatant (for failure messages)."""
        game = self.srv.table.state
        heroes = [
            f"{c.name} hp={c.hp}/{c.max_hp} xp={c.pc.xp if c.pc else 0} dead={c.dead}"
            for c in game.creatures.values()
            if c.pc is not None
        ]
        enc = game.encounter
        fight = f" fight={enc.status.value} active={enc.active_id()}" if enc is not None else ""
        tail = ",".join(m["type"] for m in self.host.conn.log[-8:])
        return "; ".join(heroes) + fight + f" in_combat={self.srv.table.in_combat} tail={tail}"

    def step(self, name: str) -> None:
        self.report.step = name
        self.report.say(f"-- {name}   [{self.party_line()[:230]}]")

    # --- campaign start --------------------------------------------------------------------

    async def start_campaign(self) -> None:
        self.step("host_start")
        mark = self.host.conn.mark()
        await self.host.conn.send({"type": "host_start"})
        wait = self.timeout * 3
        await self.host.conn.wait_for(lambda m: m["type"] == "narration_done", wait, mark)
        await self.settle()
        phase = self.state().get("phase")
        if phase != "play":
            self.report.fail(f"campaign did not reach phase play (phase={phase})")
        self.hub = scene_of(self.state()).get("node_id", "")

    async def probes(self) -> None:
        self.step("chaos probes")
        for message in await run_probes(self.party.chaos.conn, self.party.chaos.rng):
            self.report.fail(message)
        await self.settle()

    # --- exploration -----------------------------------------------------------------------

    async def explore_round(self, label: str) -> None:
        self.step(f"explore {label}")
        texts = [(b, explore_text(b.role, self.state(), b.rng)) for b in self.party.bots]
        gold_before = _gold(self.party.chaos)
        outcomes = await asyncio.gather(*(b.submit(t, self.timeout) for b, t in texts))
        for (bot, text), outcome in zip(texts, outcomes, strict=True):
            self.report.say(f"{bot.name}: {text[:50]!r} -> {outcome}")
        await self.settle()
        if _gold(self.party.chaos) != gold_before:
            self.report.fail(f"chaotic hero gold changed during exploration: {gold_before}")

    # --- votes and travel ------------------------------------------------------------------

    async def propose(self, proposer: Bot, text: str) -> bool:
        """Propose until the vote passes (a table talks it over and votes again), at most
        `VOTE_ATTEMPTS` times: with two voters left one decline is a tie, which fails."""
        for _ in range(VOTE_ATTEMPTS):
            if await self._propose_once(proposer, text):
                return True
        return False

    async def _propose_once(self, proposer: Bot, text: str) -> bool:
        """Submit a party action that needs a ready vote; the others vote; True if it passed."""
        marks = {b.name: b.conn.mark() for b in self.party.bots}
        outcome = await proposer.submit(text, self.timeout)
        opened = proposer.conn.of_type("vote_open", marks[proposer.name])
        if not opened:
            self.report.fail(f"{text!r} did not open a vote (outcome {outcome})")
            return False
        vote_id = opened[-1]["vote_id"]
        await asyncio.sleep(0.2)
        for bot in self.party.bots:
            if bot is not proposer:
                ready = bot.role != "chaos" or self.rng.random() < 0.7
                await bot.vote(vote_id, ready)
        done = await proposer.conn.wait_for(
            lambda m: m["type"] == "vote_closed" and m["vote_id"] == vote_id,
            self.timeout,
            marks[proposer.name],
        )
        await self.settle()
        return bool(done["passed"])

    async def travel(self, name: str) -> bool:
        self.step(f"travel to {name}")
        before = scene_of(self.state()).get("node_id")
        passed = await self.propose(self.proposer(self.party.explorer), f"I travel to {name}")
        after = scene_of(self.state()).get("node_id")
        if not passed or after == before:
            self.report.fail(f"travel to {name} did not move the party ({before} -> {after})")
            return False
        return True

    # --- combat ----------------------------------------------------------------------------

    # --- rest, level-up, region boundary ---------------------------------------------------

    def proposer(self, preferred: Bot) -> Bot:
        """`preferred` if its hero lives, else the first bot whose hero does."""
        game = self.srv.table.state

        def alive(bot: Bot) -> bool:
            hero = game.creatures.get(bot.hero_id)
            return hero is not None and not hero.dead

        return next((b for b in [preferred, *self.party.bots] if alive(b)), preferred)

    async def short_rest(self) -> None:
        self.step("short rest")
        used = self.srv.table.state.short_rests_used
        if not await self.propose(self.proposer(self.party.fighter), "I take a short rest"):
            self.report.fail("the short rest vote did not pass")
        elif self.srv.table.state.short_rests_used == used + 1:
            self.short_rests += 1

    async def level_ups(self) -> None:
        self.step("level up")
        pending = [b for b in self.party.bots if _wants_level(b)]
        for bot in pending:
            result = await level_up_bot(bot)
            self.report.say(f"{bot.name} level up -> {result}")
            if result != "ok":
                self.report.fail(
                    f"level up refused for {bot.name} ({bot.class_index}): {result}; "
                    f"{self.party_line()}"
                )
        await self.settle()
        levels = [c["level"] for c in self.state().get("party", [])]
        self.report.level = max((lv for lv in levels if lv), default=1)
        if not any(lv and lv >= 2 for lv in levels):
            self.report.fail(
                f"no hero reached level 2 by play (levels {levels}; {self.party_line()})"
            )

    def unvisited(self) -> list[str]:
        exits = scene_of(self.state()).get("exits", [])
        return [e["name"] for e in exits if not e["locked"] and not e["visited"]]

    def spoke_to_visit(self) -> str | None:
        """An unvisited unlocked exit of the hub, if the party stands in the hub."""
        if scene_of(self.state()).get("node_id") != self.hub:
            return None
        names = self.unvisited()
        return self.rng.choice(names) if names else None

    async def return_to_hub(self) -> None:
        if scene_of(self.state()).get("node_id") == self.hub:
            return
        hub_name = next(
            (
                e["name"]
                for e in scene_of(self.state()).get("exits", [])
                if e["node_id"] == self.hub
            ),
            None,
        )
        if hub_name is not None:
            await self.travel(hub_name)

    async def to_gateway(self, visited: list[str]) -> None:
        """Walk to the region gateway: the unlocked, unvisited exit that is not the hub."""
        self.step("gateway")
        if scene_of(self.state()).get("node_id") == self.hub and visited:
            await self.travel(visited[-1])
        exits = scene_of(self.state()).get("exits", [])
        gate = [e for e in exits if e["node_id"] != self.hub and not e["visited"]]
        if not gate or gate[0]["locked"]:
            self.report.notes.append(f"gateway not reachable: exits {exits}")
            return
        if await self.travel(gate[0]["name"]):
            self.report.notes.append(f"reached the gateway {gate[0]['name']}")


def _gold(bot: Bot) -> int | None:
    me = bot.me()
    return me.get("gold") if me else None


def _wants_level(bot: Bot) -> bool:
    return any(m["type"] == "level_up_available" for m in bot.conn.log)
