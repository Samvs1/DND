"""Helpers for table actor tests: a table on a manual clock, seats, outbox reading (no network)."""

from collections.abc import AsyncIterator, Iterable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aidm.dm.fake_llm import FakeLLM, FakeStep
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_settings import LlmSettings
from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.models.protocol import AnyClientMsg, AnyServerMsg
from aidm.models.protocol_client import DeviceRole, Hello
from aidm.models.protocol_server import Welcome
from aidm.models.state import GameState
from aidm.session import combat_flow
from aidm.session.persistence import CampaignStore
from aidm.session.reducer import replay
from aidm.session.table import Connection, Table
from aidm.session.table_clock import ManualClock
from aidm.session.table_core import TableConfig
from tests.ai.fake_scripts import fake_client
from tests.ai.guard_fixtures import inn_state
from tests.ai.tool_fixtures import tool_call


def disabled_llm(tmp_path: Path) -> LlmClient:
    return make_llm_client(LlmSettings(api_key=None, log_path=tmp_path / "llm.jsonl"))


def fake_llm(tmp_path: Path, script: Iterable[FakeStep] = ()) -> tuple[LlmClient, FakeLLM]:
    return fake_client(tmp_path, script)


@dataclass
class Seat:
    table: Table
    conn: Connection
    player_id: str
    token: str

    def send(self, msg: AnyClientMsg) -> None:
        self.table.submit(self.conn.id, msg)

    def drain(self) -> list[AnyServerMsg]:
        out: list[AnyServerMsg] = []
        while not self.conn.outbox.empty():
            out.append(self.conn.outbox.get_nowait())
        return out


@asynccontextmanager
async def running(
    llm: LlmClient,
    state: GameState | None = None,
    *,
    turn_seconds: float | None = 90.0,
    store: CampaignStore | None = None,
) -> AsyncIterator[tuple[Table, ManualClock]]:
    clock = ManualClock()
    config = TableConfig(clock=clock, turn_seconds=turn_seconds, store=store)
    table = Table(state if state is not None else inn_state(), llm, config)
    async with table:
        yield table, clock


async def join(table: Table, name: str, creature_id: str | None = None) -> Seat:
    conn = table.connect()
    table.submit(conn.id, Hello(name=name))
    await table.settle()
    welcome = next(m for m in drain_queue(conn) if isinstance(m, Welcome))
    if creature_id is not None:
        table.players[welcome.player_id].creature_id = creature_id
    return Seat(table, conn, welcome.player_id, welcome.token)


async def screen_seat(table: Table) -> Seat:
    """A /screen connection (M11.2 role "screen"): not seated, so no player id or token."""
    conn = table.connect()
    table.submit(conn.id, Hello(name="screen", role=DeviceRole.SCREEN))
    await table.settle()
    return Seat(table, conn, "", "")


async def join_with_token(table: Table, name: str, token: str) -> Seat:
    conn = table.connect()
    table.submit(conn.id, Hello(name=name, token=token))
    await table.settle()
    welcome = next(m for m in drain_queue(conn) if isinstance(m, Welcome))
    return Seat(table, conn, welcome.player_id, welcome.token)


def drain_queue(conn: Connection) -> list[AnyServerMsg]:
    out: list[AnyServerMsg] = []
    while not conn.outbox.empty():
        out.append(conn.outbox.get_nowait())
    return out


def of_type[T](msgs: Sequence[AnyServerMsg], kind: type[T]) -> list[T]:
    return [m for m in msgs if isinstance(m, kind)]


def types(msgs: Sequence[AnyServerMsg]) -> list[str]:
    return [m.type for m in msgs]


async def start_fight(table: Table, *monsters: str, **extra: Any) -> None:
    """Start a fight through the start_encounter DM tool inside a table job."""

    async def job() -> None:
        call = tool_call("start_encounter", monster_ids=list(monsters), **extra)
        result = execute_tool(table.state, call, ToolContext("fighter"), table.rng, table.regs)
        assert result.ok, result.error
        table.apply_all(list(result.events))
        await combat_flow.after_resolution(table, result.events)

    table.schedule(job)
    await table.settle()


def assert_replays(table: Table) -> None:
    seqs = [entry.seq for entry in table.log]
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs))) if seqs else True
    rebuilt = replay(table.initial, [entry.event for entry in table.log])
    assert rebuilt.model_dump() == table.state.model_dump()
