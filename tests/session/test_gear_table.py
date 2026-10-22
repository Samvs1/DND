"""Typed gear use at the table (M27.5): a long-rest craft proposes the rest and crafts during it,
a refused typed use goes on to the adjudicator, and a typed use applies through the rules."""

from pathlib import Path

from aidm.models.character import InventoryItem
from aidm.models.item_events import ItemUsed, LightEnded, LightLit
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import ErrorMsg, NarrationDone, Notice, VoteClosed, VoteOpen
from aidm.models.protocol_views import VoteKind
from aidm.models.state import GameState
from aidm.rules.rests import long_rest_cost
from aidm.session.reducer import apply
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import (
    assert_replays,
    disabled_llm,
    join,
    of_type,
    running,
    start_fight,
)


def _carrying(*items: str, tools: tuple[str, ...] = ()) -> GameState:
    state = inn_state()
    pc = state.creatures["fighter"].pc
    assert pc is not None
    pc.inventory += [InventoryItem(item=i, qty=1) for i in items]
    pc.tool_proficiencies = [*pc.tool_proficiencies, *tools]
    return state


def _poultices(state: GameState) -> int:
    pc = state.creatures["fighter"].pc
    assert pc is not None
    return next((e.qty for e in pc.inventory if e.item == "herbal-poultice"), 0)


async def test_herbalism_crafts_at_a_long_rest(tmp_path: Path) -> None:
    state = _carrying("herbalism-kit", tools=("herbalism-kit",))
    state.camp_supplies = 60  # the rest costs 10 per hero, the poultice 2 more
    before = state.camp_supplies
    cost = long_rest_cost(state)
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", "fighter")
        seat.send(SubmitAction(text="I brew a poultice with my herbalism kit"))
        await table.settle()
        msgs = seat.drain()
        opened = of_type(msgs, VoteOpen)
        assert [v.kind for v in opened] == [VoteKind.LONG_REST]
        assert of_type(msgs, VoteClosed)[0].passed
        assert _poultices(table.state) == 1
        assert table.state.camp_supplies == before - cost - 2
        assert of_type(msgs, NarrationDone)
        assert_replays(table)


async def test_herbalism_without_the_proficiency_rests_and_makes_nothing(tmp_path: Path) -> None:
    state = _carrying("herbalism-kit")
    state.camp_supplies = 60
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", "fighter")
        seat.send(SubmitAction(text="I brew a poultice"))
        await table.settle()
        assert _poultices(table.state) == 0
        assert table.state.camp_supplies == 60 - long_rest_cost(table.state)
        assert any("not trained" in n.text for n in of_type(seat.drain(), Notice))
        assert_replays(table)


async def test_typed_gear_use_applies_through_the_rules(tmp_path: Path) -> None:
    state = _carrying("spyglass")
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", "fighter")
        seat.send(SubmitAction(text="I use my spyglass"))
        await table.settle()
        used = [e.event for e in table.log if isinstance(e.event, ItemUsed)]
        assert [u.use_id for u in used] == ["spyglass-look"]
        assert of_type(seat.drain(), NarrationDone)
        seat.send(SubmitAction(text="I use my spyglass"))  # refused (no stacking): the AI path
        await table.settle()
        assert len([e for e in table.log if isinstance(e.event, ItemUsed)]) == 1
        assert of_type(seat.drain(), NarrationDone)
        assert_replays(table)


async def test_putting_a_light_out_in_a_fight_is_free_on_any_turn(tmp_path: Path) -> None:
    state = _carrying("lantern-hooded")
    apply(state, LightLit(creature_id="fighter", item="lantern-hooded"))
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", "fighter")
        await start_fight(table, "goblin")
        assert table.combat_active()
        seat.send(SubmitAction(text="put out my lantern"))
        await table.settle()
        ended = [e.event for e in table.log if isinstance(e.event, LightEnded)]
        assert ended == [LightEnded(creature_id="fighter", reason="doused", item="lantern-hooded")]
        assert not any(isinstance(m, ErrorMsg) for m in seat.drain())
        assert_replays(table)
