"""M15.3: the session diagnostics log: events, fields, no tokens, rotation, failing sinks."""

import json
from pathlib import Path

from starlette.testclient import TestClient

from aidm.models.commands import EndTurnCommand
from aidm.models.protocol_client import (
    CombatCommandMsg,
    CreateCharacter,
    DefeatRetry,
    Hello,
    HostStart,
)
from aidm.models.state import GameState
from aidm.session.persistence import CampaignStore
from aidm.session.session_log import FileLog, MemoryLog, SessionLog
from aidm.session.turn_clock import GRACE_SECONDS
from tests.session.defeat_fixtures import end_turns_until_over, party_of
from tests.session.server_fixtures import hello, make_app, read_until
from tests.session.table_fixtures import assert_replays, fake_llm, join, running, start_fight
from tests.unit.rules.creation_fixtures import default_choices


async def test_session_log_scripted_session_records_every_event(tmp_path: Path) -> None:
    sink = MemoryLog()
    state = party_of("fighter", hp={"fighter": 1})
    llm, _ = fake_llm(tmp_path)
    store = CampaignStore(tmp_path / "saves")
    async with running(llm, state, store=store, session_log=sink) as (table, clock):
        sam = await join(table, "Sam", "fighter")
        await start_fight(table, "wolf")
        table.disconnect(sam.conn.id)
        await table.settle()
        back = table.connect()
        table.submit(back.id, Hello(name="Sam", token=sam.token))
        await table.settle()
        table.disconnect(back.id)
        await table.settle()
        clock.advance(GRACE_SECONDS + 1)
        await table.settle()
        again = table.connect()
        table.submit(again.id, Hello(name="Sam", token=sam.token))
        await table.settle()
    kinds = {r["event"] for r in sink.records()}
    want = {"hello", "turn_prompt", "seat_released", "grace_started", "grace_ended"}
    want |= {"auto_turn"}
    assert want <= kinds, want - kinds
    hellos = sink.records("hello")
    assert hellos[0]["reconnect"] is False and hellos[1]["reconnect"] is True
    assert hellos[1]["name"] == "Sam" and hellos[1]["player_id"] == sam.player_id
    assert {"conn", "role", "last_seq"} <= hellos[0].keys()
    started = sink.records("grace_started")[0]
    assert started["player_id"] == sam.player_id and started["creature_id"] == "fighter"
    reasons = {r["reason"] for r in sink.records("grace_ended")}
    assert {"returned", "expired"} <= reasons
    assert "grace_expired" in {r["reason"] for r in sink.records("auto_turn")}
    for r in sink.records():
        assert isinstance(r["ts"], float) and r["campaign_id"]
    assert sam.token not in "\n".join(sink.lines)


async def test_session_log_defeat_retry_and_end_of_fight(tmp_path: Path) -> None:
    sink = MemoryLog()
    store = CampaignStore(tmp_path / "saves")
    state = party_of("fighter", hp={"fighter": 1})
    llm, _ = fake_llm(tmp_path)
    async with running(llm, state, store=store, session_log=sink) as (table, clock):
        sam = await join(table, "Sam", "fighter")
        await start_fight(table, "wolf")
        clock.advance(91)
        await table.settle()
        await end_turns_until_over(table, [sam])
        sam.send(DefeatRetry())
        await table.settle()
    assert sink.records("defeat") and sink.records("retry")[0]["attempt"] == 1
    assert sink.records("encounter_ended")[0]["status"]
    assert sam.token not in "\n".join(sink.lines)


async def test_session_log_timer_events(tmp_path: Path) -> None:
    sink = MemoryLog()
    llm, _ = fake_llm(tmp_path)
    async with running(llm, turn_seconds=180.0, session_log=sink) as (table, clock):
        await join(table, "Ann", "fighter")
        await join(table, "Bob", "rogue")
        await start_fight(table, "goblin", "goblin")
        clock.advance(160)
        await table.settle()
        clock.advance(30)
        await table.settle()
    assert sink.records("turn_warning") and sink.records("turn_timeout")
    prompt = sink.records("turn_prompt")[0]
    assert prompt["seconds"] == 180.0 and prompt["player_id"] and prompt["creature_id"]
    assert "timeout" in {r["reason"] for r in sink.records("auto_turn")}


def test_session_log_socket_open_and_close_code(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        hello(ws, "Sam")
        read_until(ws, "snapshot")
    lines = (tmp_path / "logs" / "session.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    opened = [r for r in rows if r["event"] == "ws_open"]
    closed = [r for r in rows if r["event"] == "ws_close"]
    assert opened and closed
    assert closed[0]["conn"] == opened[0]["conn"] and closed[0]["code"] is not None
    assert closed[0]["lived_s"] is not None and closed[0]["player_id"] is not None


def test_session_log_rotates_at_the_cap(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "session.jsonl"
    log = FileLog(path, cap_bytes=300)
    for i in range(30):
        log.emit("tick", "c1", n=i)
    rotated = path.with_name("session.1.jsonl")
    assert rotated.exists() and path.exists()
    assert path.stat().st_size < 600
    assert not path.with_name("session.2.jsonl").exists()
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[-1])["n"] == 29


class _Broken(SessionLog):
    def write(self, line: str) -> None:
        raise OSError("disk gone")


async def test_session_log_failing_sink_does_not_break_the_table(tmp_path: Path) -> None:
    llm, _ = fake_llm(tmp_path)
    state = party_of("fighter", hp={"fighter": 30})
    async with running(llm, state, session_log=_Broken()) as (table, _clock):
        await join(table, "Sam", "fighter")
        await start_fight(table, "wolf")
        assert table.turn_key is not None


async def test_session_log_campaign_start_records_source_and_problems(tmp_path: Path) -> None:
    """M16 follow-up: a campaign start logs where the plan came from, so a fallback is explained."""
    sink = MemoryLog()
    llm, _ = fake_llm(tmp_path)
    async with running(llm, GameState(campaign_id="t", seed=3), session_log=sink) as (table, _):
        ann = await join(table, "Ann")
        choices = default_choices("fighter", "human", None).model_copy(update={"name": "Ann"})
        ann.send(CreateCharacter(choices=choices))
        await table.settle()
        ann.send(HostStart())
        await table.settle()
    [row] = sink.records("campaign")
    assert row["source"] in {"model", "fallback"}
    assert isinstance(row["attempts"], int) and isinstance(row["problems"], list)
    assert ann.token not in "\n".join(sink.lines)


async def test_session_log_narration_lines_and_mid_fight_record(tmp_path: Path) -> None:
    # M20.1: every telling logs its source; a mid-fight segment is recorded in the save.
    sink = MemoryLog()
    llm, _ = fake_llm(tmp_path)
    async with running(llm, session_log=sink) as (table, _clock):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "wolf")
        enc = table.state.encounter
        assert enc is not None and table.turn_key is not None
        fight_start = len(table.log)
        active = enc.active_id() or ""
        seat = ann if table.players[ann.player_id].creature_id == active else bob
        seat.send(CombatCommandMsg(command=EndTurnCommand(actor_id=active)))
        await table.settle()
        mid = [e.event for e in table.log[fight_start:] if e.event.type == "narration_recorded"]
        assert table.in_combat and mid, "the segment told before the next prompt is recorded"
        assert_replays(table)
    lines = sink.records("narration")
    assert lines and {"source", "retried", "flags", "failure"} <= lines[0].keys()
    assert {r["source"] for r in lines} <= {"model", "mixed", "template"}
