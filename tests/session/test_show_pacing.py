"""The screen paces the table (M26.3, docs/next/GOAL_DICE.md "Timing (the hard rule)").

A screen that animates rolls reports `presented {seq}`; an AI turn waits for it (floor
`ai_turn_pause_s`, cap `show_wait_cap_s`) and a hero's turn clock starts only once the screen
presented what came before. No show-capable screen = the fixed pause, exactly as before."""

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.models.protocol_client import Presented
from aidm.models.protocol_server import ErrorMsg, TurnPrompt
from aidm.server.settings import DEFAULT_SHOW_WAIT_CAP_S, server_settings_from_env
from aidm.session import combat_flow, show_pace
from aidm.session.session_log import MemoryLog
from aidm.session.show_board import ShowBoard, WaitEnd
from aidm.session.table import Table
from aidm.session.table_clock import ManualClock
from aidm.session.table_core import TableConfig
from tests.ai.guard_fixtures import inn_state
from tests.ai.tool_fixtures import tool_call
from tests.session.table_fixtures import fake_llm, join, of_type, running, screen_seat

CAP = 8.0


async def _until(cond: Callable[[], bool], tries: int = 3000) -> None:
    for _ in range(tries):
        if cond():
            return
        await asyncio.sleep(0.001)
    raise AssertionError("condition never held")


def _schedule_fight(table: Table) -> "asyncio.Task[None]":
    """Start a fight inside a table job WITHOUT settling (the job may wait for the screen)."""

    async def job() -> None:
        call = tool_call("start_encounter", monster_ids=["wolf", "wolf"])
        result = execute_tool(table.state, call, ToolContext("fighter"), table.rng, table.regs)
        assert result.ok, result.error
        table.apply_all(list(result.events))
        await combat_flow.after_resolution(table, result.events)

    table.schedule(job)
    return asyncio.create_task(table.settle())


async def _waiting(table: Table, settle: "asyncio.Task[None]") -> int:
    await _until(lambda: table.shows.waiting_for is not None or settle.done())
    assert table.shows.waiting_for is not None, "the table did not wait for the screen"
    return table.shows.waiting_for


def _moved_on(table: Table, held: int) -> Callable[[], bool]:
    """The next turn began (it always logs events) or a hero's turn is open."""
    return lambda: len(table.log) > held or table.turn_key is not None


async def _capable_screen(table: Table) -> str:
    screen = await screen_seat(table)
    screen.send(Presented(seq=0))
    await table.settle()
    return screen.conn.id


# --- ShowBoard on a manual clock ------------------------------------------------------------


async def test_board_without_capable_screen_and_zero_floor_does_not_wait() -> None:
    clock = ManualClock()
    assert await ShowBoard().wait(clock, 9, 0.0, CAP) is WaitEnd.NONE
    assert clock.pending() == 0  # no timer: exactly the old path


async def test_board_without_capable_screen_waits_exactly_the_floor() -> None:
    clock, board = ManualClock(), ShowBoard()
    task = asyncio.create_task(board.wait(clock, 9, 1.5, CAP))
    await asyncio.sleep(0)
    clock.advance(1.49)
    await asyncio.sleep(0)
    assert not task.done()
    clock.advance(0.01)
    assert await task is WaitEnd.FLOOR
    assert clock.pending() == 0


async def test_board_waits_for_the_screen_but_never_less_than_the_floor() -> None:
    clock, board = ManualClock(), ShowBoard()
    board.report("s1", 3)
    task = asyncio.create_task(board.wait(clock, 9, 1.5, CAP))
    await asyncio.sleep(0)
    board.report("s1", 9)  # shown early: the floor still holds
    await asyncio.sleep(0)
    assert not task.done()
    clock.advance(1.5)
    assert await task is WaitEnd.PRESENTED


async def test_board_cap_ends_the_wait() -> None:
    clock, board = ManualClock(), ShowBoard()
    board.report("s1", 3)
    task = asyncio.create_task(board.wait(clock, 9, 1.5, CAP))
    await asyncio.sleep(0)
    clock.advance(CAP - 0.01)
    await asyncio.sleep(0)
    assert not task.done()
    clock.advance(0.01)
    assert await task is WaitEnd.CAP
    assert board.waiting_for is None and clock.pending() == 0


async def test_board_waits_for_every_capable_screen_and_a_leaver_stops_counting() -> None:
    clock, board = ManualClock(), ShowBoard()
    board.report("s1", 0)
    board.report("s2", 0)
    task = asyncio.create_task(board.wait(clock, 4, 0.0, CAP))
    await asyncio.sleep(0)
    board.report("s1", 4)
    await asyncio.sleep(0)
    assert not task.done()  # s2 is still behind
    board.drop("s2")  # it left: the waiter wakes at once
    assert await task is WaitEnd.PRESENTED


# --- the table actor ------------------------------------------------------------------------


async def test_capable_screen_holds_the_ai_turn_until_it_presents(tmp_path: Path) -> None:
    llm, _ = fake_llm(tmp_path)
    async with running(llm) as (table, _clock):  # no seats: every turn is an AI turn
        await _capable_screen(table)
        settle = _schedule_fight(table)
        seq = await _waiting(table, settle)
        assert seq == show_pace.last_shown_seq(table) > 0
        held = len(table.log)
        await asyncio.sleep(0.01)
        assert len(table.log) == held and table.shows.waiting_for == seq
        conn = next(iter(table.shows.seen))
        table.submit(conn, Presented(seq=seq))
        await _until(lambda: len(table.log) > held)
        settle.cancel()


async def test_cap_ends_the_wait_for_a_stuck_screen(tmp_path: Path) -> None:
    llm, _ = fake_llm(tmp_path)
    sink = MemoryLog()
    async with running(llm, session_log=sink) as (table, clock):
        await _capable_screen(table)
        settle = _schedule_fight(table)
        await _waiting(table, settle)
        held = len(table.log)
        clock.advance(CAP - 0.1)
        await asyncio.sleep(0.01)
        assert len(table.log) == held
        clock.advance(0.1)
        await _until(lambda: len(table.log) > held)
        assert sink.records("show_wait_capped")
        settle.cancel()


async def test_no_capable_screen_gives_exactly_the_floor(tmp_path: Path) -> None:
    llm, _ = fake_llm(tmp_path)
    clock = ManualClock()
    config = TableConfig(clock=clock, ai_turn_pause_s=1.5)
    async with Table(inn_state(), llm, config) as table:
        await screen_seat(table)  # a screen that never sent `presented` does not pace
        settle = _schedule_fight(table)
        await _waiting(table, settle)
        held = len(table.log)
        clock.advance(1.49)
        await asyncio.sleep(0.01)
        assert len(table.log) == held
        clock.advance(0.01)
        await _until(lambda: len(table.log) > held)
        settle.cancel()


async def test_capable_screen_that_disconnects_releases_the_wait(tmp_path: Path) -> None:
    llm, _ = fake_llm(tmp_path)
    async with running(llm) as (table, _clock):
        conn = await _capable_screen(table)
        settle = _schedule_fight(table)
        await _waiting(table, settle)
        table.disconnect(conn)
        await asyncio.wait_for(settle, timeout=30)  # the whole fight runs on: nobody paces it
        assert table.shows.seen == {} and table.shows.waiting_for is None


async def test_presented_from_a_player_connection_is_ignored(tmp_path: Path) -> None:
    llm, _ = fake_llm(tmp_path)
    async with running(llm) as (table, _clock):
        ann = await join(table, "Ann", "fighter")
        ann.drain()
        ann.send(Presented(seq=3))
        stranger = table.connect()  # never said hello
        table.submit(stranger.id, Presented(seq=3))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg) == []
        assert stranger.outbox.empty()
        assert table.shows.seen == {}


@pytest.mark.parametrize("release", ["presented", "cap"])
async def test_turn_clock_starts_only_after_the_screen_presented(
    tmp_path: Path, release: str
) -> None:
    llm, _ = fake_llm(tmp_path)
    async with running(llm) as (table, clock):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        conn = await _capable_screen(table)
        settle = _schedule_fight(table)
        for _ in range(40):
            seq = await _waiting(table, settle)
            if table.turn_key is None:  # an AI turn: let the cap pass, the screen stays behind
                clock.advance(CAP)
                await _until(_moved_on(table, len(table.log)))
                continue
            break
        assert table.turn_key is not None and table.turn_clock.deadline is None
        assert of_type(ann.drain() + bob.drain(), TurnPrompt) == []
        if release == "presented":
            table.submit(conn, Presented(seq=seq))
        else:
            clock.advance(CAP)
        await _until(lambda: table.turn_clock.deadline is not None)
        assert of_type(ann.drain(), TurnPrompt)  # sent in the same step as the clock start
        assert table.turn_left() == pytest.approx(90.0)
        settle.cancel()


def test_show_wait_cap_setting() -> None:
    # M26.3: the longest wait for the screen's show; 8 s unless AIDM_SHOW_WAIT_CAP (0..20).
    assert server_settings_from_env({}).show_wait_cap_s == DEFAULT_SHOW_WAIT_CAP_S == 8.0
    assert server_settings_from_env({"AIDM_SHOW_WAIT_CAP": "3"}).show_wait_cap_s == 3.0
    assert server_settings_from_env({"AIDM_SHOW_WAIT_CAP": "99"}).show_wait_cap_s == 20.0
    assert server_settings_from_env({"AIDM_SHOW_WAIT_CAP": "-1"}).show_wait_cap_s == 0.0
    assert server_settings_from_env({"AIDM_SHOW_WAIT_CAP": "nan"}).show_wait_cap_s == 8.0
    assert server_settings_from_env({"AIDM_SHOW_WAIT_CAP": "soon"}).show_wait_cap_s == 8.0


def test_presented_message_shape() -> None:
    assert Presented(seq=0).type == "presented"
    with pytest.raises(ValueError):
        Presented(seq=-1)
