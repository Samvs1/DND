"""Persistence: snapshot + events.jsonl round trip, replay on disk, recovery (M6.3)."""

from pathlib import Path

from aidm.models.protocol_client import HostPause, HostResume, SubmitAction
from aidm.session.persistence import (
    CampaignLoadError,
    CampaignStore,
    new_game_state,
    valid_campaign_id,
)
from aidm.session.reducer import replay
from aidm.session.restore import restore
from aidm.session.table import Table
from aidm.session.table_core import TableConfig
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import disabled_llm, join, menu_llm, pick, running

SEARCH = pick(("search:investigation", [], None))  # "I search behind the hearth" (M36.10a)


async def _play(tmp_path: Path, store: CampaignStore) -> Table:
    llm = menu_llm(tmp_path, SEARCH)[0]
    async with running(llm, inn_state(), store=store) as (table, _):
        host = await join(table, "Ann", "fighter")
        host.send(SubmitAction(text="I search behind the hearth"))
        await table.settle()
        host.send(HostPause())
        host.send(HostResume())
        host.send(SubmitAction(text="look around"))
        await table.settle()
        return table


async def test_round_trip_and_replay_from_disk_equals_snapshot(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    table = await _play(tmp_path, store)
    assert table.log
    cid = table.state.campaign_id
    loaded = store.load(cid)
    assert not loaded.recovered and not loaded.notes
    assert loaded.state.model_dump() == table.state.model_dump()
    assert [e.seq for e in loaded.log] == [e.seq for e in table.log]
    rebuilt = replay(loaded.initial, [e.event for e in loaded.log])
    assert rebuilt.model_dump() == loaded.state.model_dump()
    assert loaded.state.event_count == table.state.event_count
    seat = loaded.meta.seats[0]
    assert (seat.name, seat.creature_id, seat.is_host) == ("Ann", "fighter", True)
    lines = (store.root / cid / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(table.log)


async def test_restore_rebuilds_a_table_with_the_same_seats(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    table = await _play(tmp_path, store)
    token = next(iter(table.players.values())).token
    loaded = store.load(table.state.campaign_id)
    config = TableConfig(store=store)
    fresh = Table(new_game_state(), disabled_llm(tmp_path), config)
    restore(fresh, loaded)
    assert fresh.state.model_dump() == table.state.model_dump()
    assert [p.token for p in fresh.players.values()] == [token]
    assert [e.seq for e in fresh.log] == [e.seq for e in table.log]
    assert fresh.state.event_count == loaded.state.event_count
    fresh_ids = {fresh.next_id("p") for _ in range(3)}
    assert not fresh_ids & set(fresh.players)


async def test_corrupt_snapshot_is_recovered_by_replay(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    table = await _play(tmp_path, store)
    folder = store.root / table.state.campaign_id
    (folder / "snapshot.json").write_text("{not json", encoding="utf-8")
    loaded = store.load(table.state.campaign_id)
    assert loaded.recovered
    assert any("snapshot" in n for n in loaded.notes)
    assert loaded.state.model_dump() == table.state.model_dump()
    assert loaded.meta.seats


async def test_stale_snapshot_loses_to_the_log(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    table = await _play(tmp_path, store)
    folder = store.root / table.state.campaign_id
    snap = (folder / "snapshot.json").read_text(encoding="utf-8")
    edited = snap.replace('"camp_supplies":', '"camp_supplies":1000000,"x":', 1)
    (folder / "snapshot.json").write_text(edited, encoding="utf-8")
    loaded = store.load(table.state.campaign_id)
    assert loaded.state.model_dump() == table.state.model_dump()
    assert loaded.recovered


async def test_partial_last_line_is_tolerated_and_repaired(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    table = await _play(tmp_path, store)
    cid = table.state.campaign_id
    path = store.root / cid / "events.jsonl"
    text = path.read_text(encoding="utf-8")
    last = text.splitlines()[-1]
    path.write_text(text + last[: len(last) // 2], encoding="utf-8")
    loaded = store.load(cid)
    assert len(loaded.log) == len(table.log)
    assert loaded.state.model_dump() == table.state.model_dump()
    repaired = path.read_text(encoding="utf-8")
    assert repaired.endswith("\n") and len(repaired.splitlines()) == len(table.log)


async def test_a_cut_log_replays_to_an_earlier_state(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    table = await _play(tmp_path, store)
    cid = table.state.campaign_id
    path = store.root / cid / "events.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    loaded = store.load(cid)
    assert len(loaded.log) == len(lines) - 1
    assert loaded.state.event_count == table.state.event_count - 1
    assert loaded.recovered


async def test_atomic_writes_leave_no_temp_files(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    table = await _play(tmp_path, store)
    folder = store.root / table.state.campaign_id
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["events.jsonl", "initial.json", "snapshot.json", "table.json"]
    assert not list(folder.glob("*.tmp")) and not list(folder.glob(".*tmp"))


async def test_list_campaigns_and_bad_ids(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    assert store.list_campaigns() == []
    table = await _play(tmp_path, store)
    listing = store.list_campaigns()
    assert [i.campaign_id for i in listing] == [table.state.campaign_id]
    assert listing[0].seq == table.state.event_count
    assert not valid_campaign_id("../x") and not valid_campaign_id("a/b")
    for bad in ("../x", "missing"):
        try:
            store.load(bad)
        except CampaignLoadError:
            continue
        raise AssertionError("expected CampaignLoadError")


async def test_autosave_after_each_resolved_action(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    llm = menu_llm(tmp_path, SEARCH, pick(other=""))[0]  # the lever: the storyteller's
    async with running(llm, inn_state(), store=store) as (table, _):
        host = await join(table, "Ann", "fighter")
        counts: list[int] = []
        for text in ("I search behind the hearth", "I study the rusted lever"):
            host.send(SubmitAction(text=text))
            await table.settle()
            counts.append(store.load(table.state.campaign_id).state.event_count)
        assert counts[0] <= counts[1] == table.state.event_count
