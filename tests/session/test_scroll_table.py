"""M27.7 scrolls at the table: read one in a fight (the hotbar command), out of a fight (typed),
at someone you are talking to (the point-of-no-return confirm, then the opening strike reads it),
and a wizard's copy into the spellbook from the Spellbook tab (`copy_scroll`)."""

from pathlib import Path

from aidm.dm.fake_llm import fake_calls, fake_text
from aidm.models.combat_events import SpellCast
from aidm.models.commands import UseItemCommand
from aidm.models.encounter import Side
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import GoldChanged, HpChanged, InventoryChanged
from aidm.models.item_events import ItemUsed
from aidm.models.protocol_client import ConfirmHostile, CopyScroll, SubmitAction
from aidm.models.protocol_server import ErrorCode, ErrorMsg, Notice
from aidm.models.state import GameState
from aidm.models.world_events import HostileActPending
from aidm.session.reducer import apply, replay
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import (
    assert_replays,
    disabled_llm,
    fake_llm,
    join,
    of_type,
    running,
)
from tests.unit.rules.combat_fixtures import ScriptedRng, do, economy, monster
from tests.unit.rules.item_fixtures import CAVE, gear_fight, hero, qty


def _carrying(cid: str, *items: str, gold: int = 0) -> GameState:
    state = inn_state()
    for item in items:
        apply(state, InventoryChanged(creature_id=cid, item=item, delta=1, qty=1))
    if gold:
        apply(state, GoldChanged(creature_id=cid, delta=gold, gold=gold))
    return state


def test_read_sleep_from_the_hotbar_in_a_fight() -> None:
    state = gear_fight(
        CAVE, hero(gear=["scroll-of-sleep"]), (monster("gob", hp=5), Side.HOSTILE, "b")
    )
    initial = state.model_copy(deep=True)
    cmd = UseItemCommand(actor_id="hero", item="scroll-of-sleep", target_zone="b")
    events = do(state, cmd, ScriptedRng(8, 8, 8, 8, 8))  # 5d8 = 40 HP of sleep
    assert [e.target_zone for e in events if isinstance(e, SpellCast)] == ["b"]
    assert "asleep" in [c.name for c in state.creatures["gob"].conditions]
    assert qty(state, "hero", "scroll-of-sleep") == 0 and not economy(state, "hero").action
    assert replay(initial, events) == state


def test_read_a_damage_scroll_from_the_hotbar_in_a_fight() -> None:
    gob = monster("gob", hp=30)
    state = gear_fight(CAVE, hero(gear=["scroll-of-magic-missile"]), (gob, Side.HOSTILE, "b"))
    cmd = UseItemCommand(actor_id="hero", item="scroll-of-magic-missile", target_id="gob")
    do(state, cmd, ScriptedRng(4, 4, 4))  # three darts of 1d4+1 (SRD 5.1 Magic Missile)
    assert state.creatures["gob"].hp == 30 - 3 * 5
    assert qty(state, "hero", "scroll-of-magic-missile") == 0


async def test_read_a_scroll_out_of_a_fight(tmp_path: Path) -> None:
    state = _carrying("fighter", "scroll-of-cure-wounds")
    apply(
        state,
        HpChanged(creature_id="fighter", delta=-10, new_hp=state.creatures["fighter"].hp - 10),
    )
    hp = state.creatures["fighter"].hp
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I read the scroll of cure wounds"))
        await table.settle()
        assert table.state.creatures["fighter"].hp > hp
        assert qty(table.state, "fighter", "scroll-of-cure-wounds") == 0
        assert_replays(table)


async def test_a_harmful_scroll_at_someone_you_talk_to_asks_are_you_sure(tmp_path: Path) -> None:
    item = "scroll-of-fire-bolt"
    read = {"actor": "fighter", "item": item, "target": "npc-mira"}
    start = {"against_npcs": ["npc-mira"], "opening_strike_on": "npc-mira", "opening_attack": item}
    script = [fake_calls([("use_item", read)]), fake_calls([("start_encounter", start)])]
    llm, _ = fake_llm(tmp_path, [*script, fake_text("Fire leaps from the page!")])
    async with running(llm, _carrying("fighter", item)) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I read the scroll of fire bolt at Mira"))
        await table.settle()
        events = [entry.event for entry in table.log]
        assert any(isinstance(e, HostileActPending) for e in events)
        assert not any(isinstance(e, EncounterStarted) for e in events)
        assert qty(table.state, "fighter", item) == 1  # nothing happens before the yes
        ann.send(ConfirmHostile())
        await table.settle()
        events = [entry.event for entry in table.log]
        casts = [e for e in events if isinstance(e, SpellCast)]
        assert casts and casts[0].caster_id == "fighter" and casts[0].spell_id == "fire-bolt"
        assert [e.item for e in events if isinstance(e, ItemUsed)] == [item]
        assert qty(table.state, "fighter", item) == 0
        assert_replays(table)


async def test_a_wizard_copies_a_scroll_from_the_spellbook_tab(tmp_path: Path) -> None:
    state = _carrying("wizard", "scroll-of-color-spray", gold=60)
    before = state.creatures["wizard"].pc
    assert before is not None
    gold = before.gold
    async with running(disabled_llm(tmp_path), state) as (table, _):
        cel = await join(table, "Cel", "wizard")
        cel.send(CopyScroll(item_id="scroll-of-color-spray"))
        await table.settle()
        pc = table.state.creatures["wizard"].pc
        assert pc is not None and "color-spray" in pc.spellbook
        assert pc.gold == gold - 50  # SRD 5.1: 50 gp per spell level (1st level)
        assert qty(table.state, "wizard", "scroll-of-color-spray") == 0
        assert any("spellbook" in n.text for n in of_type(cel.drain(), Notice))
        assert_replays(table)


async def test_a_non_wizard_cannot_copy_a_scroll(tmp_path: Path) -> None:
    state = _carrying("fighter", "scroll-of-magic-missile", gold=60)
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(CopyScroll(item_id="scroll-of-magic-missile"))
        await table.settle()
        error = of_type(ann.drain(), ErrorMsg)[0]
        assert error.code is ErrorCode.REFUSED and error.refusal == "scroll_no_scroll_copy"
        assert qty(table.state, "fighter", "scroll-of-magic-missile") == 1
