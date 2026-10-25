"""Table actor: gear, level up, gifts, pause and item use through protocol messages (M6.2)."""

from pathlib import Path

from aidm.models.events import HpChanged, InventoryChanged
from aidm.models.leveling import LevelUpChoices
from aidm.models.protocol_client import (
    Drop,
    Equip,
    HostPause,
    HostResume,
    LevelUp,
    RequestSheet,
    SubmitAction,
    Unequip,
    UseItem,
)
from aidm.models.protocol_server import ErrorCode, ErrorMsg, Notice, SheetMsg, Snapshot
from aidm.models.state import GameState
from aidm.rules.leveling import gain_xp, xp_for_level
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
)

POTION = "potion-of-healing"


async def test_gear_messages_and_equip_text(tmp_path: Path) -> None:
    llm = menu_llm(tmp_path, pick(("equip:shield", [], None)), storyteller_down=True)[0]
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(Unequip(item_id="shield"))
        await table.settle()
        assert table.state.creatures["fighter"].ac == 16
        snap = of_type(ann.drain(), Snapshot)[-1]
        assert next(p for p in snap.state.party if p.id == "fighter").ac == 16
        ann.send(SubmitAction(text="equip my shield"))
        await table.settle()
        assert table.state.creatures["fighter"].ac == 18
        assert of_type(ann.drain(), Notice)
        ann.send(Equip(item_id="greataxe"))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg)[0].code is ErrorCode.REFUSED
        assert_replays(table)


async def test_level_up_needs_xp_then_applies(tmp_path: Path) -> None:
    state = inn_state()
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(LevelUp(choices=LevelUpChoices()))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg)[0].code is ErrorCode.REFUSED
    state = inn_state()
    for event in gain_xp(state.creatures["fighter"], xp_for_level(2)):
        apply(state, event)
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(LevelUp(choices=LevelUpChoices()))
        await table.settle()
        hero = table.state.creatures["fighter"]
        assert hero.pc is not None and hero.pc.level == 2, of_type(ann.drain(), ErrorMsg)
        assert_replays(table)


async def test_pause_holds_the_queue_and_combat_messages(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        bob.send(HostPause())
        ann.send(HostPause())
        await table.settle()
        assert table.paused
        assert of_type(bob.drain(), ErrorMsg)[0].code is ErrorCode.NOT_HOST
        ann.send(SubmitAction(text="look around"))
        await table.settle()
        assert table.queue and table.resolving is None
        ann.send(HostResume())
        await table.settle()
        assert not table.queue and not table.paused


async def test_request_sheet_drop_and_refusal_codes(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(RequestSheet())
        await table.settle()
        sheets = of_type(ann.drain(), SheetMsg)
        assert sheets and sheets[0].creature_id == "fighter" and sheets[0].level_up is None
        sheet = sheets[0].sheet
        assert sheet.ac == table.state.creatures["fighter"].ac
        assert all(line.category for line in sheet.inventory)
        ann.send(Equip(item_id="greataxe"))
        await table.settle()
        refusal = of_type(ann.drain(), ErrorMsg)[0]
        assert refusal.code is ErrorCode.REFUSED and refusal.refusal == "not_carried"
        ann.send(Drop(item_id="dungeoneers-pack"))
        await table.settle()
        pc = table.state.creatures["fighter"].pc
        assert pc is not None and all(r.item != "dungeoneers-pack" for r in pc.inventory)
        assert_replays(table)


async def test_sheet_offers_level_up_options_when_ready(tmp_path: Path) -> None:
    state = inn_state()
    for event in gain_xp(state.creatures["fighter"], xp_for_level(2)):
        apply(state, event)
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(RequestSheet())
        await table.settle()
        sheet = of_type(ann.drain(), SheetMsg)[0]
        assert sheet.level_up is not None and sheet.level_up.level == 2


def _potions(state: GameState) -> int:
    pc = state.creatures["fighter"].pc
    assert pc is not None
    return sum(r.qty for r in pc.inventory if r.item == POTION)


async def test_use_potion_outside_combat(tmp_path: Path) -> None:
    state = inn_state()
    apply(state, InventoryChanged(creature_id="fighter", item=POTION, delta=2, qty=2))
    apply(state, HpChanged(creature_id="fighter", delta=-11, new_hp=1))
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(UseItem(item_id=POTION, target_id="rogue"))
        await table.settle()
        # M27.7 owner rule: a potion given at full health is drunk and wasted, and says so.
        notes = [n.text for n in of_type(ann.drain(), Notice)]
        assert _potions(table.state) == 1 and any("no special effect" in n for n in notes)
        ann.send(UseItem(item_id=POTION, target_id="nobody"))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg)[0].refusal == "unknown_target"
        ann.send(UseItem(item_id=POTION))
        await table.settle()
        assert table.state.creatures["fighter"].hp > 1 and _potions(table.state) == 0
        assert of_type(ann.drain(), Notice)
        assert_replays(table)
