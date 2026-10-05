"""The table actor: one per campaign (SPEC 5 Concurrency, 10).

Two asyncio tasks per table:
- the INBOX task reads `Inbound` items (client messages, closed connections, fired timers) in
  order and handles them at once when they only read state or touch table bookkeeping
  (hello, ping, queueing an action, votes, chat, suggestions, hit chances, host routing);
  everything that changes the game becomes a job;
- the WORKER task runs jobs one at a time. It is the only code that mutates `GameState`
  (through `TableCore.apply` -> THE reducer, with a monotonic `seq`), so the long LLM awaits
  inside a job (adjudication, narration, campaign generation) never race another mutation,
  while the inbox stays responsive (players can queue, vote and chat during narration).
After every job: a `snapshot`, `host_stats` for the host, and the next queued action.
A job that raises is logged and answered with an in-fiction fallback notice: never silent,
never a raw error.

Socket handlers (M6.4) only call `connect()`, `submit()` and `disconnect()`; tests call
`settle()` to wait until the table is idle.

Public API: `Table(state, llm, config)` (`start()`, `stop()`, `async with`, `connect()`,
`submit(conn_id, msg)`, `disconnect(conn_id)`, `settle()`), `Connection`, `FALLBACK_NOTICE`.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from types import TracebackType
from typing import Any

from aidm.dm.llm_client import LlmClient
from aidm.models import protocol_client as c
from aidm.models.protocol import AnyClientMsg, AnyServerMsg
from aidm.models.protocol_server import ErrorCode, ErrorMsg, Notice, NoticeKind, Pong
from aidm.models.state import GameState
from aidm.session import combat_flow, explore, host, lobby, party_actions, relay, sheet_view, votes
from aidm.session.stats import send_host_stats
from aidm.session.table_core import (
    ClientIn,
    Closed,
    Inbound,
    Job,
    Player,
    TableConfig,
    TableCore,
    TimerFired,
)

_LOG = logging.getLogger(__name__)
FALLBACK_NOTICE = "The tale stumbles for a moment, but the world holds. Try that again."
BAD_INPUT = "That did not work. Please try again."

type Immediate = Callable[[TableCore, Player, Any], None]
type JobMaker = Callable[[TableCore, Player, Any], Job]

IMMEDIATE: dict[type, Immediate] = {
    c.SubmitAction: explore.submit_action,
    c.Vote: lambda core, p, m: votes.cast_vote(core, p, m.vote_id, m.ready),
    c.RollAbilities: lambda core, p, m: lobby.roll(core, p),
    c.Chat: relay.chat,
    c.Suggestion: relay.suggest,
    c.RequestHitChances: relay.hit_chances_for,
    c.RequestSheet: lambda core, p, m: sheet_view.send_sheet(core, p),
    c.ExportCharacter: lambda core, p, m: lobby.export_hero(core, p),
    **{cls: host.host_message for cls in c.HOST_MESSAGES},
}

JOBS: dict[type, JobMaker] = {
    c.CreateCharacter: lambda core, p, m: partial(lobby.create, core, p, m),
    c.ImportCharacter: lambda core, p, m: partial(lobby.import_hero, core, p, m),
    c.CombatCommandMsg: lambda core, p, m: partial(combat_flow.player_command, core, p, m.command),
    c.ConfirmHostile: lambda core, p, m: partial(explore.confirm_hostile, core, p),
    c.CancelHostile: lambda core, p, m: partial(explore.cancel_hostile, core, p),
    c.AnswerOffer: lambda core, p, m: partial(party_actions.answer, core, p, m),
    c.LevelUp: lambda core, p, m: partial(party_actions.level, core, p, m),
    c.ShopBuy: lambda core, p, m: partial(party_actions.buy, core, p, m),
    c.ShopSell: lambda core, p, m: partial(party_actions.sell, core, p, m),
    c.Give: lambda core, p, m: partial(party_actions.give, core, p, m),
    c.Equip: lambda core, p, m: partial(party_actions.equip, core, p, m),
    c.Unequip: lambda core, p, m: partial(party_actions.unequip, core, p, m),
    c.Drop: lambda core, p, m: partial(party_actions.drop, core, p, m),
    c.UseItem: lambda core, p, m: partial(party_actions.use_item, core, p, m),
}

PAUSABLE = (c.CombatCommandMsg, c.ConfirmHostile, c.AnswerOffer, c.Give)


@dataclass(frozen=True)
class Connection:
    id: str
    outbox: asyncio.Queue[AnyServerMsg]


class Table(TableCore):
    def __init__(self, state: GameState, llm: LlmClient, config: TableConfig | None = None) -> None:
        super().__init__(state, llm, config)
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        if not self._tasks:
            self._tasks = [
                asyncio.create_task(self._inbox_loop()),
                asyncio.create_task(self._worker_loop()),
            ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        self.autosave()
        combat_flow.end_player_turn(self)
        if self.vote is not None and self.vote.timer is not None:
            self.vote.timer.cancel()

    async def __aenter__(self) -> "Table":
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.stop()

    def connect(self) -> Connection:
        conn = Connection(self.next_id("c"), asyncio.Queue())
        self.outboxes[conn.id] = conn.outbox
        return conn

    def submit(self, conn_id: str, msg: AnyClientMsg) -> None:
        self.inbox.put_nowait(ClientIn(conn_id, msg))

    def disconnect(self, conn_id: str) -> None:
        self.inbox.put_nowait(Closed(conn_id))

    async def settle(self) -> None:
        while True:
            await self.inbox.join()
            await self.jobs.join()
            if self.inbox.empty() and self.jobs.empty():
                return

    async def _inbox_loop(self) -> None:
        while True:
            item = await self.inbox.get()
            try:
                self._dispatch(item)
            except Exception:
                _LOG.exception("table inbox handler failed")
                if isinstance(item, ClientIn):
                    self.send_conn(item.conn_id, ErrorMsg(code=ErrorCode.INVALID, text=BAD_INPUT))
            finally:
                self.inbox.task_done()

    async def _worker_loop(self) -> None:
        while True:
            job = await self.jobs.get()
            try:
                await job()
            except Exception:
                _LOG.exception("table job failed")
                self.broadcast(Notice(kind=NoticeKind.FALLBACK, text=FALLBACK_NOTICE))
            finally:
                self._after_job()
                self.jobs.task_done()

    def _after_job(self) -> None:
        self.autosave()
        self.broadcast_snapshot()
        send_host_stats(self)
        explore.kick_resolver(self)

    def _dispatch(self, item: Inbound) -> None:
        if isinstance(item, Closed):
            lobby.closed(self, item.conn_id)
        elif isinstance(item, TimerFired):
            self._timer(item)
        else:
            self._client(item.conn_id, item.msg)

    def _timer(self, fired: TimerFired) -> None:
        if fired.kind == "vote":
            votes.vote_timeout(self, fired.key)
        elif fired.kind == "turn":
            key = fired.key
            self.schedule(lambda: combat_flow.turn_timeout(self, key))

    def _client(self, conn_id: str, msg: AnyClientMsg) -> None:
        if isinstance(msg, c.Hello):
            lobby.hello(self, conn_id, msg)
            self.autosave()
            return
        if isinstance(msg, c.Ping):
            self.send_conn(conn_id, Pong())
            return
        player = self.player_for(conn_id)
        if player is None:
            self.send_conn(conn_id, ErrorMsg(code=ErrorCode.NOT_JOINED, text="Join first."))
            return
        immediate = IMMEDIATE.get(type(msg))
        if immediate is not None:
            immediate(self, player, msg)
            return
        if self.paused and isinstance(msg, PAUSABLE):
            self.error(player.id, ErrorCode.PAUSED, "The game is paused.")
            return
        maker = JOBS.get(type(msg))
        if maker is not None:
            self.schedule(maker(self, player, msg))
