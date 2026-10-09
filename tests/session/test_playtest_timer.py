"""M15.1 (c): the turn timer: off at a solo table, 3 min default, host setting, countdown,
a 30 s warning; the careful auto-turn only when the timer runs out."""

import json
from pathlib import Path

from aidm.models.protocol_client import HostTurnTimer
from aidm.models.protocol_server import ErrorCode, ErrorMsg, Notice, Snapshot, TurnPrompt
from aidm.session.persistence import TABLE, CampaignStore
from aidm.session.table import Table
from aidm.session.table_core import TableConfig
from aidm.session.turn_clock import WARN_TEXT
from tests.session.defeat_fixtures import party_of
from tests.session.table_fixtures import (
    Seat,
    disabled_llm,
    join,
    of_type,
    running,
    start_fight,
)


def _owner(table: Table, seats: list[Seat]) -> Seat:
    enc = table.state.encounter
    assert enc is not None and table.turn_key is not None
    return next(s for s in seats if table.players[s.player_id].creature_id == enc.active_id())


def test_playtest_turn_timer_default_is_three_minutes() -> None:
    assert TableConfig().turn_seconds == 180.0


async def test_playtest_solo_table_has_no_turn_timer(tmp_path: Path) -> None:
    state = party_of("fighter", hp={"fighter": 40})
    async with running(disabled_llm(tmp_path), state) as (table, clock):
        sam = await join(table, "Sam", "fighter")
        await start_fight(table, "wolf")
        key, before = table.turn_key, table.state.event_count
        prompts = of_type(sam.drain(), TurnPrompt)
        assert prompts and prompts[-1].seconds is None
        clock.advance(3600)
        await table.settle()
        assert table.turn_key == key and table.state.event_count == before
        assert table.snapshot().state.floor.seconds_left is None


async def test_playtest_turn_timer_countdown_and_warning(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), turn_seconds=180.0) as (table, clock):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "goblin", "goblin")
        on = _owner(table, [ann, bob])
        key = table.turn_key
        prompt = of_type(on.drain(), TurnPrompt)[-1]
        assert prompt.seconds == 180.0
        clock.advance(100)
        await table.settle()
        assert table.snapshot().state.floor.seconds_left == 80.0
        clock.advance(50)
        await table.settle()
        warned = [n.text for n in of_type(on.drain(), Notice)]
        assert WARN_TEXT in warned
        assert table.turn_key == key
        clock.advance(30)
        await table.settle()
        assert table.turn_key != key, "the careful auto-turn when the timer runs out"


async def test_playtest_host_turn_timer_setting(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    async with running(disabled_llm(tmp_path), store=store) as (table, clock):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "goblin", "goblin")
        key = table.turn_key
        assert table.snapshot().state.floor.seconds_left == 90.0
        bob.send(HostTurnTimer(seconds=0))
        await table.settle()
        assert of_type(bob.drain(), ErrorMsg)[-1].code is ErrorCode.NOT_HOST
        ann.send(HostTurnTimer(seconds=0))
        await table.settle()
        assert of_type(ann.drain(), Snapshot)[-1].state.turn_timer == 0
        meta = json.loads((store.folder(table.state.campaign_id) / TABLE).read_text("utf-8"))
        assert meta["turn_timer"] == 0
        assert table.snapshot().state.floor.seconds_left is None, "Off stops the running clock"
        clock.advance(3600)
        await table.settle()
        assert table.turn_key == key, "the timer is off: nobody's turn is taken"
        ann.send(HostTurnTimer(seconds=300))
        await table.settle()
        assert table.snapshot().state.turn_timer == 300
        assert table.snapshot().state.floor.seconds_left == 300.0
        loaded = store.load(table.state.campaign_id)
        assert loaded.meta.turn_timer == 300
