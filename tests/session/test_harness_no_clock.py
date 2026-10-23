"""M29.4 H1: with the playtest settings (no turn timer, a day of grace) a slow player is never
auto-played, however long the gap between commands."""

from pathlib import Path

from aidm.models.protocol_server import Notice
from aidm.session.table import Table
from aidm.session.table_core import TableConfig
from tests.session.table_fixtures import (
    ManualClock,
    Seat,
    disabled_llm,
    inn_state,
    join,
    of_type,
    start_fight,
)

DAY = 86400.0


async def test_slow_player_is_never_auto_played(tmp_path: Path) -> None:
    clock = ManualClock()
    config = TableConfig(clock=clock, turn_seconds=None, grace_seconds=DAY)
    async with Table(inn_state(), disabled_llm(tmp_path), config) as table:
        seats: list[Seat] = [await join(table, "Ann", "fighter"), await join(table, "Bob", "rogue")]
        await start_fight(table, "goblin", "goblin")
        key = table.turn_key
        enc = table.state.encounter
        assert key is not None and enc is not None
        active = enc.active_id()
        owner = next(s for s in seats if table.players[s.player_id].creature_id == active)
        table.disconnect(owner.conn.id)  # every harness command is a short-lived connection
        await table.settle()
        clock.advance(600.0)  # an AI tester thinking for ten minutes
        await table.settle()
        assert table.turn_key == key
        notices = [n.text for s in seats for n in of_type(s.drain(), Notice)]
        assert not any("hesitates" in t for t in notices)
