"""M29.5b typed healing out of a fight (docs/playtests/M29_round1.md G2 / G17 / G33), each
reproduced from its live save: the engine heals, or refuses in plain words; never prose only."""

from pathlib import Path

from aidm.models.combat_events import SpellCast
from aidm.models.events import HpChanged, InventoryChanged, ResourceSet
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import NarrationDone
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import (
    Step,
    assert_replays,
    join,
    menu_llm,
    of_type,
    pick,
    running,
)


async def _typed(
    tmp_path: Path, run: str, seq: int, hero: str, text: str, *steps: Step, other: bool = False
) -> list[object]:
    """`steps` (or `other`): the menu chooser's reading (M36.10a); the AI is otherwise down."""
    state = replay_until(run, seq)
    choice = pick(*steps, other="" if other else None)
    llm = menu_llm(tmp_path, choice, storyteller_down=True)[0]
    async with running(llm, state, interpreter="menu") as (table, _):
        seat = await join(table, "Ann", hero)
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert of_type(seat.drain(), NarrationDone), "the table always answers"
        assert_replays(table)
        return [e.event for e in table.log if e.seq >= start]


def _healed(events: list[object], who: str) -> int:
    return sum(e.delta for e in events if isinstance(e, HpChanged) and e.creature_id == who)


async def test_m29_typed_drink_heals_through_the_potion_path(tmp_path: Path) -> None:
    """p6 875-884: "Brienne drinks the restorative draught" (3/20 HP) was prose only."""
    for text in ("Brienne drinks the restorative draught", "use restorative draught"):
        drink: Step = ("item:restorative-draught", ["pc-p2"], None)
        events = await _typed(tmp_path, "p6", 875, "pc-p2", text, drink)
        used = [e for e in events if isinstance(e, InventoryChanged)]
        assert [(u.item, u.delta) for u in used] == [("restorative-draught", -1)]
        assert _healed(events, "pc-p2") > 0


async def test_m29_typed_potion_for_a_dead_hero_is_refused(tmp_path: Path) -> None:
    """p6 873: a draught poured for a dead hero is refused by the rules; nothing is used."""
    text = "I pour the Restorative Draught into dead Tamsin's mouth to bring her back to life"
    events = await _typed(tmp_path, "p6", 873, "pc-p2", text, other=True)  # no such entry
    assert not any(isinstance(e, InventoryChanged | HpChanged) for e in events)


async def test_m29_typed_potion_and_poultice_on_an_ally(tmp_path: Path) -> None:
    """p2 662-666: Rook (0 HP) was given his own potion, then Brienne's poultice: prose only."""
    text = "Elowen kneels by Rook and pours his Potion of Healing between his lips."
    feed: Step = ("feed:potion-of-healing", ["pc-p6"], None)
    events = await _typed(tmp_path, "p2", 662, "pc-p4", text, feed)
    used = [(e.creature_id, e.item) for e in events if isinstance(e, InventoryChanged)]
    assert used == [("pc-p6", "potion-of-healing")] and _healed(events, "pc-p6") > 0
    text = (
        "Brienne binds Rook's wounds with her Herbal Poultice and holds the pack against his side."
    )
    bind: Step = ("item:herbal-poultice", ["pc-p6"], None)
    events = await _typed(tmp_path, "p2", 664, "pc-p2", text, bind)
    used = [(e.creature_id, e.item) for e in events if isinstance(e, InventoryChanged)]
    assert used == [("pc-p2", "herbal-poultice")] and _healed(events, "pc-p6") > 0


async def test_m29_typed_cure_wounds_casts_with_a_slot(tmp_path: Path) -> None:
    """p3 590-591: "Brienne casts cure wounds on Tamsin" (10/20 HP) narrated a heal, HP and
    slots unchanged. The spell engine casts it now: a slot is spent and Tamsin heals."""
    cure: Step = ("cast:cure-wounds", ["pc-p8"], None)
    events = await _typed(tmp_path, "p3", 590, "pc-p2", "Brienne casts cure wounds on Tamsin", cure)
    assert [e.spell_id for e in events if isinstance(e, SpellCast)] == ["cure-wounds"]
    slots = [e for e in events if isinstance(e, ResourceSet) and e.creature_id == "pc-p2"]
    assert slots and slots[0].key.startswith("spell-slot-")
    assert _healed(events, "pc-p8") > 0
