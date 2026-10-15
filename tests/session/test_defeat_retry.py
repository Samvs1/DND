"""Defeat choices (M11.1): retry from a checkpoint, load a save, new adventure, reload."""

from pathlib import Path

from aidm.models.defeat import CheckpointFile
from aidm.models.events import AnyEvent, LoggedEvent
from aidm.models.protocol_client import DefeatLoad, DefeatNew, DefeatRetry, SubmitAction
from aidm.models.protocol_server import ErrorMsg, Notice, Snapshot, StoryHistory, Welcome
from aidm.models.protocol_views import TablePhase
from aidm.session.persistence import CHECKPOINTS, EVENTS, CampaignStore, TableMeta
from aidm.session.reducer import replay
from aidm.session.restore import restore
from aidm.session.table import Table
from aidm.session.table_core import TableConfig
from tests.session.defeat_fixtures import end_turns_until_over, hurt, party_of, travel
from tests.session.table_fixtures import (
    assert_replays,
    disabled_llm,
    join,
    join_with_token,
    of_type,
    running,
    start_fight,
    types,
)


def _saved_log(path: Path) -> list[LoggedEvent]:
    lines = path.read_text("utf-8").splitlines()
    return [LoggedEvent.model_validate_json(line) for line in lines if line.strip()]


async def test_retry_restores_the_checkpoint_exactly_and_keeps_seats(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    async with running(disabled_llm(tmp_path), party_of("fighter"), store=store) as (table, _):
        sam = await join(table, "Sam", "fighter")
        await travel(table, "forest")
        marker = table.state.event_count
        expected = table.state.model_copy(deep=True)
        await hurt(table, "fighter", 999)
        assert table.phase is TablePhase.DEFEATED
        discarded = [e for e in table.log if e.seq >= marker]
        sam.drain()
        sam.send(DefeatRetry())
        await table.settle()
        assert table.phase is TablePhase.PLAY and table.state.defeat is None
        assert table.state.model_dump() == expected.model_dump()
        assert all(e.seq < marker for e in table.log)
        rebuilt = replay(table.initial, [e.event for e in table.log])
        assert rebuilt.model_dump() == table.state.model_dump()
        msgs = sam.drain()
        assert types(msgs)[:4] == ["welcome", "lobby_roster", "snapshot", "story_history"]
        welcome = of_type(msgs, Welcome)[0]
        assert (welcome.player_id, welcome.token) == (sam.player_id, sam.token)
        assert table.players[sam.player_id].creature_id == "fighter"
        assert of_type(msgs, StoryHistory) and of_type(msgs, Snapshot)[-1].state.phase == "play"
        assert any("tries again" in n.text for n in of_type(msgs, Notice))
        folder = store.folder(table.state.campaign_id)
        assert _saved_log(folder / EVENTS) == table.log
        assert _saved_log(folder / "events.1.defeat") == discarded
        marks = CheckpointFile.model_validate_json((folder / CHECKPOINTS).read_text("utf-8"))
        assert marks.retries == 1 and marks.checkpoints[-1].seq == marker
        loaded = store.load(table.state.campaign_id)
        assert not loaded.recovered and loaded.state.model_dump() == table.state.model_dump()
        sam.send(SubmitAction(text="I look around again"))
        await table.settle()
        assert not [e for e in of_type(sam.drain(), ErrorMsg) if e.refusal == "defeated"]


def _after(log: list[LoggedEvent], marker: int) -> list[AnyEvent]:
    return [e.event for e in log if e.seq >= marker]


async def test_retried_fight_resumes_with_new_dice_and_can_differ(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    state = party_of("fighter", hp={"fighter": 1})
    async with running(disabled_llm(tmp_path), state, store=store) as (table, _):
        sam = await join(table, "Sam", "fighter")
        # The wolf is surprised, so the fighter's turn always comes first on every retry (the
        # dice decide the rest; M21 changed how many rolls a fight's map uses).
        await start_fight(table, "wolf", surprise="hostile")
        marker = table.checkpoints.checkpoints[-1].seq
        await end_turns_until_over(table, [sam])
        assert table.phase is TablePhase.DEFEATED
        first = _after(table.log, marker)
        sam.send(DefeatRetry())
        await table.settle()
        assert table.phase is TablePhase.PLAY and table.in_combat and table.turn_key
        assert table.state.creatures["fighter"].hp == 1, "back at the fight start"
        await end_turns_until_over(table, [sam])
        second = _after(table.log, marker)
        assert second != first, "a reseeded retry plays the fight differently"
        assert table.phase is TablePhase.DEFEATED
        assert_replays(table)
        sam.send(DefeatRetry())
        await table.settle()
        folder = store.folder(table.state.campaign_id)
        assert (folder / "events.2.defeat").is_file() and table.checkpoints.retries == 2
        assert table.phase is TablePhase.PLAY
        assert_replays(table)


async def test_defeat_new_and_defeat_load(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    other = party_of("fighter")
    other.campaign_id = "other-save"
    store.save("other-save", initial=other, events=[], state=other, meta=TableMeta())
    async with running(disabled_llm(tmp_path), party_of("fighter"), store=store) as (table, _):
        sam = await join(table, "Sam", "fighter")
        await hurt(table, "fighter", 999)
        assert table.phase is TablePhase.DEFEATED
        sam.send(DefeatLoad(campaign_id="other-save"))
        await table.settle()
        assert table.phase is TablePhase.PLAY and table.state.campaign_id == "other-save"
        sam.send(DefeatNew())
        await table.settle()
        refused = of_type(sam.drain(), ErrorMsg)[-1]
        assert refused.refusal == "not_defeated" and table.state.campaign_id == "other-save"
        await hurt(table, "fighter", 999)
        sam.send(DefeatNew())
        await table.settle()
        assert table.phase is TablePhase.LOBBY and table.state.campaign_id != "other-save"
        seat = next(p for p in table.players.values() if p.token == sam.token)
        assert seat.is_host and seat.connected, "the person keeps a (host) seat by token"


async def test_a_defeated_save_reloads_defeated(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    llm = disabled_llm(tmp_path)
    async with running(llm, party_of("fighter"), store=store) as (table, _):
        sam = await join(table, "Sam", "fighter")
        await travel(table, "forest")
        await hurt(table, "fighter", 999)
        cid, token = table.state.campaign_id, sam.token
    fresh = Table(party_of("fighter"), llm, TableConfig(store=store))
    restore(fresh, store.load(cid))
    async with fresh:
        assert fresh.phase is TablePhase.DEFEATED and fresh.state.defeat is not None
        mark = fresh.retry_checkpoint()
        assert mark is not None and mark.label == "Whisperwood, on arrival"
        back = await join_with_token(fresh, "Sam", token)
        snap = fresh.snapshot().state
        assert snap.phase is TablePhase.DEFEATED and snap.defeat and snap.checkpoint
        back.send(SubmitAction(text="I wake up"))
        await fresh.settle()
        assert of_type(back.drain(), ErrorMsg)[-1].refusal == "defeated"
        back.send(DefeatRetry())
        await fresh.settle()
        assert fresh.phase is TablePhase.PLAY and fresh.state.defeat is None
