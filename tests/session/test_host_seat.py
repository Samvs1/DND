"""M17.1: stale seats are refused and the host role follows the table (owner request)."""

from pathlib import Path

from aidm.models.protocol_client import Hello
from aidm.models.protocol_server import (
    ErrorCode,
    ErrorMsg,
    HostStats,
    LobbyRoster,
    Notice,
    NoticeKind,
    Welcome,
)
from aidm.models.state import GameState
from aidm.session.host_seat import HOST_AWAY_S
from aidm.session.persistence import CampaignStore
from aidm.session.restore import restore
from aidm.session.session_log import MemoryLog
from aidm.session.table import Table
from aidm.session.table_clock import ManualClock
from aidm.session.table_core import TableConfig
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import (
    Seat,
    disabled_llm,
    drain_queue,
    join,
    join_with_token,
    of_type,
    running,
)


def lobby() -> GameState:
    return GameState(campaign_id="t", seed=1)


def hosts(table: Table) -> list[str]:
    return [p.id for p in table.players.values() if p.is_host]


def host_notices(seat: Seat) -> list[str]:
    msgs = of_type(seat.drain(), Notice)
    return [n.text for n in msgs if n.kind is NoticeKind.HOST]


async def leave(table: Table, seat: Seat) -> None:
    table.disconnect(seat.conn.id)
    await table.settle()


async def test_stale_token_is_refused_and_not_seated(tmp_path: Path) -> None:
    sink = MemoryLog()
    async with running(disabled_llm(tmp_path), lobby(), session_log=sink) as (table, _):
        conn = table.connect()
        table.submit(conn.id, Hello(name="Old Page", token="from-an-earlier-run"))
        await table.settle()
        msgs = drain_queue(conn)
        assert [m.code for m in of_type(msgs, ErrorMsg)] == [ErrorCode.UNKNOWN_SEAT]
        assert not of_type(msgs, Welcome)
        assert table.players == {} and conn.id not in table.conn_player
        refused = sink.records("hello_refused")
        assert refused and refused[0]["reason"] == "unknown_seat"
        # Pressing Join again (no token) on the same connection seats normally, as the host.
        table.submit(conn.id, Hello(name="Old Page"))
        await table.settle()
        welcome = of_type(drain_queue(conn), Welcome)[0]
        assert welcome.is_host and hosts(table) == [welcome.player_id]


async def test_stale_token_on_a_seated_connection_keeps_the_seat(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), lobby()) as (table, _):
        ann = await join(table, "Ann")
        ann.send(Hello(name="Ann", token="unknown"))
        await table.settle()
        assert of_type(ann.drain(), Welcome)[0].player_id == ann.player_id
        assert len(table.players) == 1


async def test_lobby_host_leaves_and_the_earliest_connected_seat_hosts(tmp_path: Path) -> None:
    sink = MemoryLog()
    async with running(disabled_llm(tmp_path), lobby(), session_log=sink) as (table, _):
        ann, bob, cid = await join(table, "Ann"), await join(table, "Bob"), await join(table, "Cid")
        for seat in (bob, cid):
            seat.drain()
        await leave(table, ann)
        assert hosts(table) == [bob.player_id]
        bob_msgs = bob.drain()
        assert "Bob is now the host." in [n.text for n in of_type(bob_msgs, Notice)]
        assert of_type(bob_msgs, Welcome)[-1].is_host
        assert of_type(bob_msgs, HostStats)
        roster = of_type(bob_msgs, LobbyRoster)[-1]
        assert [p.is_host for p in roster.players] == [False, True, False]
        assert "Bob is now the host." in host_notices(cid)
        moved = sink.records("host_moved")[-1]
        assert moved["from_id"] == ann.player_id and moved["to_id"] == bob.player_id
        assert moved["reason"] == "host_left_lobby"
        back = await join_with_token(table, "Ann", ann.token)
        assert hosts(table) == [bob.player_id], "a returning former host is an ordinary player"
        assert not table.players[back.player_id].is_host


async def test_ghost_seat_first_page_leaves_next_joiner_hosts(tmp_path: Path) -> None:
    """Playtest 2026-10-10: a page seated first and left before anyone else joined."""
    sink = MemoryLog()
    async with running(disabled_llm(tmp_path), lobby(), session_log=sink) as (table, _):
        ghost = await join(table, "Ghost")
        await leave(table, ghost)
        assert hosts(table) == [ghost.player_id], "nobody else is here: nothing moves"
        owner = await join(table, "Owner")
        assert hosts(table) == [owner.player_id]
        moved = sink.records("host_moved")
        assert [(m["from_id"], m["to_id"]) for m in moved] == [(ghost.player_id, owner.player_id)]


async def test_play_host_drop_under_a_minute_keeps_the_role(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), inn_state()) as (table, clock):
        ann, bob = await join(table, "Ann"), await join(table, "Bob")
        await leave(table, ann)
        clock.advance(HOST_AWAY_S - 5)
        await table.settle()
        assert hosts(table) == [ann.player_id]
        await join_with_token(table, "Ann", ann.token)
        clock.advance(10)
        await table.settle()
        assert hosts(table) == [ann.player_id], "back in time: still the host"
        assert "Bob is now the host." not in host_notices(bob)


async def test_play_host_away_over_a_minute_hands_over(tmp_path: Path) -> None:
    sink = MemoryLog()
    async with running(disabled_llm(tmp_path), inn_state(), session_log=sink) as (table, clock):
        ann, bob = await join(table, "Ann"), await join(table, "Bob")
        await leave(table, ann)
        clock.advance(HOST_AWAY_S + 1)
        await table.settle()
        assert hosts(table) == [bob.player_id]
        assert "Bob is now the host." in host_notices(bob)
        assert sink.records("host_moved")[-1]["reason"] == "host_away"


async def test_play_host_away_alone_moves_when_someone_connects(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), inn_state()) as (table, clock):
        ann, bob = await join(table, "Ann"), await join(table, "Bob")
        await leave(table, bob)
        await leave(table, ann)
        clock.advance(HOST_AWAY_S * 2)
        await table.settle()
        assert hosts(table) == [ann.player_id], "nobody connected: nothing moves"
        back = await join_with_token(table, "Bob", bob.token)
        assert hosts(table) == [back.player_id]


async def test_loaded_save_host_never_returns_first_player_hosts(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    llm = disabled_llm(tmp_path)
    async with running(llm, inn_state(), store=store) as (table, _):
        ann, bob = await join(table, "Ann"), await join(table, "Bob")
        assert table.autosave(force=True)
        cid = table.state.campaign_id
    sink = MemoryLog()
    fresh = Table(inn_state(), llm, TableConfig(clock=ManualClock(), store=store, session_log=sink))
    restore(fresh, store.load(cid))
    async with fresh:
        assert hosts(fresh) == [ann.player_id]
        back = await join_with_token(fresh, "Bob", bob.token)
        assert hosts(fresh) == [back.player_id] == [bob.player_id]
        assert sink.records("host_moved")[-1]["reason"] == "host_not_returned"
        again = await join_with_token(fresh, "Ann", ann.token)
        assert not fresh.players[again.player_id].is_host
    seats = store.load(cid).meta.seats
    assert [s.is_host for s in seats] == [False, True], "table.json follows the move"


async def test_exactly_one_host_through_many_comings_and_goings(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), lobby()) as (table, _):
        seats = [await join(table, name) for name in ("Ann", "Bob", "Cid", "Dee")]
        for seat in seats[:3]:
            await leave(table, seat)
            assert len(hosts(table)) == 1
            assert table.players[hosts(table)[0]].connected
        for seat in seats[:3]:
            await join_with_token(table, seat.conn.id, seat.token)
            assert hosts(table) == [seats[3].player_id]
