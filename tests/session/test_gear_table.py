"""Typed gear use at the table (M27.5): a long-rest craft proposes the rest and crafts during it,
a refused typed use goes on to the adjudicator, and a typed use applies through the rules.
M27.6: gear in a fight, typed or from the hotbar's combat command."""

from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.dm.llm_client import LlmClient
from aidm.models.character import InventoryItem
from aidm.models.combat_events import AttackRolled, ZoneSurfaceAdded
from aidm.models.commands import UseItemCommand
from aidm.models.item_events import ItemUsed, LightEnded, LightLit
from aidm.models.protocol_client import CombatCommandMsg, SubmitAction
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
    menu_llm,
    of_type,
    pick,
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


BREW = pick(("use:herbalism-kit-craft", [], None))  # "I brew a poultice" (M36.10a)


def _menu(tmp_path: Path, *picks: FakeStep) -> LlmClient:
    """The menu interpreter's picks; every other AI call fails as with no key."""
    return menu_llm(tmp_path, *picks, storyteller_down=True)[0]


async def test_herbalism_crafts_at_a_long_rest(tmp_path: Path) -> None:
    state = _carrying("herbalism-kit", tools=("herbalism-kit",))
    state.camp_supplies = 60  # the rest costs 10 per hero, the poultice 2 more
    before = state.camp_supplies
    cost = long_rest_cost(state)
    async with running(_menu(tmp_path, BREW), state, interpreter="menu") as (table, _):
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
    async with running(_menu(tmp_path, BREW), state, interpreter="menu") as (table, _):
        seat = await join(table, "Ann", "fighter")
        seat.send(SubmitAction(text="I brew a poultice"))
        await table.settle()
        assert _poultices(table.state) == 0
        assert table.state.camp_supplies == 60 - long_rest_cost(table.state)
        assert any("not trained" in n.text for n in of_type(seat.drain(), Notice))
        assert_replays(table)


async def test_typed_gear_use_applies_through_the_rules(tmp_path: Path) -> None:
    state = _carrying("spyglass")
    look = pick(("use:spyglass-look", [], None))
    async with running(_menu(tmp_path, look, look), state, interpreter="menu") as (table, _):
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


async def test_typed_throw_in_a_fight_runs_the_item_rules(tmp_path: Path) -> None:
    # M27.6: "I throw the acid at the goblin" on the hero's own turn is THE interpreter's
    # thrown attack (no AI involved); the vial is used up, hit or miss.
    state = _carrying("acid-vial")
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", "fighter")
        await start_fight(table, "goblin")
        enc = table.state.encounter
        assert enc is not None and enc.active_id() == "fighter"
        seat.send(SubmitAction(text="I throw the acid at the goblin"))
        await table.settle()
        used = [e.event for e in table.log if isinstance(e.event, ItemUsed)]
        assert [u.use_id for u in used] == ["acid-vial-throw"]
        assert any(isinstance(e.event, AttackRolled) for e in table.log)
        pc = table.state.creatures["fighter"].pc
        assert pc is not None and all(e.item != "acid-vial" for e in pc.inventory)
        assert not any(isinstance(m, ErrorMsg) for m in seat.drain())
        assert_replays(table)


async def test_hotbar_gear_use_goes_through_the_combat_command(tmp_path: Path) -> None:
    state = _carrying("oil-flask", "holy-water-flask")
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", "fighter")
        await start_fight(table, "goblin")
        oil = UseItemCommand(actor_id="fighter", item="oil-flask", target_zone="gully")
        seat.send(CombatCommandMsg(command=oil))
        await table.settle()
        added = [e.event for e in table.log if isinstance(e.event, ZoneSurfaceAdded)]
        assert [(a.zone_id, a.surface.kind) for a in added] == [("gully", "oil")]
        assert not of_type(seat.drain(), ErrorMsg)
        holy = UseItemCommand(actor_id="fighter", item="holy-water-flask", target_id="goblin-1")
        seat.send(CombatCommandMsg(command=holy))
        await table.settle()
        errors = of_type(seat.drain(), ErrorMsg)
        assert [e.refusal for e in errors] == ["gear_refused"]  # the action is already spent
        assert_replays(table)
