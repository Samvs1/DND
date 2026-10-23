"""M29.5b G37 (found in M29.5a): a seat restored by a load or a retry gets the reconnect grace."""

from pathlib import Path

from aidm.session import turn_clock
from aidm.session.persistence import CampaignStore
from aidm.session.restore import restore
from aidm.session.turn_clock import GRACE_SECONDS
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import disabled_llm, join, running


async def test_m29_restored_seat_gets_a_fresh_grace(tmp_path: Path) -> None:
    """G37 (M29.5a): seats restored by a load or a retry came back with no connection and no
    `left_at`, so `grace_left` was 0 and their heroes were auto-played at once. Such a seat now
    counts as gone at the restore: the usual reconnect grace, then the safe turn."""
    store = CampaignStore(tmp_path / "saves")
    async with running(disabled_llm(tmp_path), inn_state(), store=store) as (table, clock):
        await join(table, "Ann", "fighter")
        assert table.autosave(force=True)
        restore(table, store.load(table.state.campaign_id))
        ann = next(p for p in table.players.values() if p.creature_id == "fighter")
        assert not ann.connected and ann.left_at is None
        assert turn_clock.grace_left(table, ann) == GRACE_SECONDS
        clock.advance(GRACE_SECONDS - 1)
        assert turn_clock.grace_left(table, ann) == 1
        clock.advance(2)
        assert turn_clock.grace_left(table, ann) == 0
