"""M31.1a V2, V6, V7 (docs/playtests/M31_round4.md): typed spells, drinks and gear lines out of a
fight, each on the real round-4 state where the line was typed."""

from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.models.combat_events import SpellCast
from aidm.models.events import AnyEvent, HpChanged, ResourceSet
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import Notice
from aidm.models.state import GameState
from aidm.models.world_events import EquipmentChanged
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import (
    Seat,
    assert_replays,
    join,
    menu_llm,
    pick,
    running,
)

RUN = "m31-r4-typed"


def _typed(seq: int) -> tuple[str, str]:
    event = logged(RUN, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


async def _turn(
    tmp_path: Path, state: GameState, actor: str, text: str, choice: FakeStep
) -> tuple[list[AnyEvent], GameState, list[str]]:
    """`choice`: the menu chooser's reading (M36.10a); the AI is otherwise down."""
    llm = menu_llm(tmp_path, choice, storyteller_down=True)[0]
    async with running(llm, state) as (table, _):
        seat: Seat = await join(table, "Ann", actor)
        seat.drain()
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
        notes = [m.text for m in seat.drain() if isinstance(m, Notice)]
        return events, table.state, notes


async def test_m31_scene_cast_with_people_near_spends_the_slot(tmp_path: Path) -> None:
    actor, text = _typed(79)
    state = replay_until(RUN, 79)
    before = state.creatures[actor].resources["spell-slot-1"].current
    burn = pick(("cast:burning-hands", [], None))
    events, after, _ = await _turn(tmp_path, state, actor, text, burn)
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.at_scene) for e in cast] == [("burning-hands", True)]
    assert after.creatures[actor].resources["spell-slot-1"].current == before - 1
    assert not any(isinstance(e, HpChanged) and e.creature_id == actor for e in events)


async def test_m31_murmured_healing_word_heals_and_spends(tmp_path: Path) -> None:
    actor, text = _typed(86)
    word = pick(("cast:healing-word", ["pc-p6"], None), colour="to soothe his singed arms")
    events, _, _ = await _turn(tmp_path, replay_until(RUN, 86), actor, text, word)
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.target_ids) for e in cast] == [("healing-word", ("pc-p6",))]
    assert any(isinstance(e, ResourceSet) and e.key == "spell-slot-1" for e in events)


async def test_m31_compound_gear_line_keeps_the_valid_half(tmp_path: Path) -> None:
    """M36.10a: the longsword is already away, so the menu has no stow of it: the chooser picks
    the shield's stow alone, and the shield is stowed."""
    actor, text = _typed(1333)
    state = replay_until(RUN, 1333)
    pc = state.creatures[actor].pc
    assert pc is not None
    pc.equipped = pc.equipped.model_copy(update={"main_hand": None})  # already sheathed
    stow = pick(("unequip:shield", [], None))
    events, after, _ = await _turn(tmp_path, state, actor, text, stow)
    worn = after.creatures[actor].pc
    assert worn is not None and worn.equipped.shield is None
    assert any(isinstance(e, EquipmentChanged) for e in events)
