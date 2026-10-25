"""The session runners of the menu's new acts (M36.4): taking from a fallen hero's pack (round 6
Y14), Second Wind out of a fight and a counted take, each run through `intent_turn.run_intent` at
a real table, applied by the one reducer and replayed equal (nothing typed: the typed-line path
reaches these acts from M36.6)."""

from pathlib import Path

from aidm.models.combat_events import FeatureUsed
from aidm.models.events import InventoryChanged, ResourceSet
from aidm.models.item_events import HandedOver
from aidm.models.protocol_server import ErrorMsg
from aidm.models.protocol_views import QueueEntry
from aidm.models.state import GameState
from aidm.models.world import WorldItem
from aidm.models.world_events import ItemPlaced, ItemRemoved
from aidm.rules.acts import FeatureUseIntent, Intent, LootIntent, TakeIntent
from aidm.rules.item_grants import carried_qty
from aidm.session.intent_turn import run_intent
from aidm.session.reducer import apply
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, of_type, running

POTION = "potion-of-healing"


async def _run(tmp_path: Path, state: GameState, hero: str, intent: Intent) -> list[object]:
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", hero)
        start = table.state.event_count
        player = table.players[seat.player_id]
        entry = QueueEntry(player_id=seat.player_id, creature_id=hero, text="menu act")

        async def job() -> None:
            await run_intent(table, player, table.state.creatures[hero], entry, intent)

        table.schedule(job)
        await table.settle()
        assert_replays(table)
        errors = of_type(seat.drain(), ErrorMsg)
        return [*errors, *(e.event for e in table.log if e.seq >= start)]


async def test_v1_y14_menu_loot_runs_at_the_table(tmp_path: Path) -> None:
    state = replay_until("m35-r6-full", 469)
    apply(state, InventoryChanged(creature_id="pc-p8", item=POTION, delta=1, qty=1))
    events = await _run(tmp_path, state, "pc-p2", LootIntent("pc-p2", "pc-p8", POTION))
    handed = [e for e in events if isinstance(e, HandedOver)]
    assert len(handed) == 1 and handed[0].taken and handed[0].item == POTION
    moved = [(e.creature_id, e.delta) for e in events if isinstance(e, InventoryChanged)]
    assert moved == [("pc-p8", -1), ("pc-p2", 1)]


async def test_menu_loot_refusal_is_plain_at_the_table(tmp_path: Path) -> None:
    state = replay_until("m35-r6-full", 469)
    events = await _run(tmp_path, state, "pc-p2", LootIntent("pc-p2", "pc-p8", POTION))
    assert isinstance(events[0], ErrorMsg) and "does not carry" in events[0].text


async def test_menu_second_wind_out_of_a_fight_at_the_table(tmp_path: Path) -> None:
    state = replay_until("m35-r6-full", 469)
    state.creatures["pc-p2"].hp = 9
    events = await _run(tmp_path, state, "pc-p2", FeatureUseIntent("pc-p2", "second-wind"))
    used = [e for e in events if isinstance(e, FeatureUsed)]
    assert [u.feature for u in used] == ["second-wind"]
    spent = [e for e in events if isinstance(e, ResourceSet)]
    assert spent and spent[0].resource.current == 0


async def test_menu_counted_take_at_the_table(tmp_path: Path) -> None:
    state = replay_until("m35-r6-full", 469)
    here = state.world.current_node
    bolts = WorldItem(
        id="bolts", name="Crossbow Bolt", catalog_id="crossbow-bolt", qty=3, node_id=here
    )
    apply(state, ItemPlaced(item=bolts))
    have = carried_qty(state.creatures["pc-p2"], "crossbow-bolt")
    events = await _run(tmp_path, state, "pc-p2", TakeIntent("pc-p2", "bolts", 2))
    assert ItemRemoved(item_id="bolts", qty=2) in events
    gained = [e for e in events if isinstance(e, InventoryChanged)]
    assert gained[0].qty == have + 2
