"""M30.2b: no free spells by typing (the M30.2 live probe: "I cast misty step to reach the roof"
outside a fight got `no_mechanics`, so the spell worked and no slot was spent).

A typed cast of a spell the hero has ready always goes through the engine on the real table:
a spell aimed at no creature is cast at the scene (`rules.spells.scene_cast`, the slot spent,
nobody moved between places), a cantrip spends nothing and is still cast, no slot left is refused
plainly, and a hostile spell with an NPC here stays the storyteller's (an attack, or a fight)."""

from pathlib import Path

from aidm.dm.cast_intent import CastIntent
from aidm.dm.precheck import precheck
from aidm.models.combat_events import SpellCast
from aidm.models.events import AnyEvent, ResourceSet
from aidm.models.protocol_client import SubmitAction
from aidm.models.state import GameState
from aidm.models.world_events import NarrationRecorded, PartyMoved
from tests.ai.tool_fixtures import party_state
from tests.session.table_fixtures import assert_replays, disabled_llm, join, running
from tests.sim.sim_setup import build_party
from tests.unit.rules.item_fixtures import DOCKS, at

BLINK = "I cast misty step to reach the roof of the warehouse"
SLOT2 = "spell-slot-2"


def _docks() -> GameState:
    """The live probe's scene: the docks (three NPCs stand here), a level-3 party, Misty Step
    prepared by the wizard."""
    state = at(DOCKS)
    build_party(state, 3)
    wizard = state.creatures["wizard"].pc
    assert wizard is not None
    wizard.spellbook.append("misty-step")
    wizard.prepared.append("misty-step")
    return state


async def _typed(
    tmp_path: Path, state: GameState, actor: str, text: str
) -> tuple[list[AnyEvent], GameState]:
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", actor)
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        return [e.event for e in table.log if e.seq >= start], table.state


def _told(events: list[AnyEvent]) -> list[str]:
    return [e.text for e in events if isinstance(e, NarrationRecorded)]


async def test_m30_typed_misty_step_spends_the_slot(tmp_path: Path) -> None:
    state = _docks()
    node = state.world.current_node
    slots = state.creatures["wizard"].resources[SLOT2].current
    assert precheck(state, "wizard", BLINK) == CastIntent("wizard", "misty-step", (), True)
    events, after = await _typed(tmp_path, state, "wizard", BLINK)
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.cast_level, e.at_scene) for e in cast] == [("misty-step", 2, True)]
    assert any(isinstance(e, ResourceSet) and e.key == SLOT2 for e in events)
    assert after.creatures["wizard"].resources[SLOT2].current == slots - 1
    # a teleport outside a fight moves nobody between places: travel stays travel
    assert not any(isinstance(e, PartyMoved) for e in events)
    assert after.world.current_node == node
    told = " ".join(_told(events))
    assert "Misty Step" in told and "no one to another place" in told


async def test_m30_typed_cantrip_at_the_scene_spends_nothing(tmp_path: Path) -> None:
    state = party_state(3)  # the town square: nobody else stands here, no offer waits
    text = "I cast fire bolt at the old scarecrow"
    assert precheck(state, "wizard", text) == CastIntent("wizard", "fire-bolt", (), True)
    events, _ = await _typed(tmp_path, state, "wizard", text)
    cast = [e for e in events if isinstance(e, SpellCast)]
    assert [(e.spell_id, e.cast_level, e.at_scene) for e in cast] == [("fire-bolt", 0, True)]
    assert not any(isinstance(e, ResourceSet) for e in events)
    assert any("Fire Bolt" in line and "strikes no one" in line for line in _told(events))


async def test_m30_typed_cast_with_no_slot_left_is_refused_plainly(tmp_path: Path) -> None:
    state = _docks()
    slots = state.creatures["wizard"].resources
    slots[SLOT2] = slots[SLOT2].model_copy(update={"current": 0})
    events, _ = await _typed(tmp_path, state, "wizard", BLINK)
    assert not any(isinstance(e, SpellCast | ResourceSet) for e in events)
    assert _told(events) == ["You have no spell slot left for that."]


async def test_m30_typed_unready_scene_spell_is_refused_plainly(tmp_path: Path) -> None:
    state = _docks()  # the fighter has no spells at all
    events, _ = await _typed(tmp_path, state, "fighter", "I cast misty step onto the roof")
    assert not any(isinstance(e, SpellCast | ResourceSet) for e in events)
    assert _told(events) == ["You cannot cast spells."]


def test_m30_hostile_spell_aimed_at_an_npc_keeps_the_old_path() -> None:
    state = _docks()  # Dessa, Odalys and Tobin stand on the docks
    assert precheck(state, "wizard", "I cast fire bolt at Tobin") is None
    # M31.1a V2: people standing near do not stop a cast at scenery (round 4, typed 79)
    assert precheck(state, "wizard", "I cast fire bolt at the crates") == CastIntent(
        "wizard", "fire-bolt", (), True
    )
    # with nobody here a hostile spell has no one to strike: it is cast at the scene
    empty = party_state(3)
    assert precheck(empty, "wizard", "I cast fire bolt at the crates") == CastIntent(
        "wizard", "fire-bolt", (), True
    )


def test_m30_scene_spell_needs_its_name_after_the_cast_word() -> None:
    state = party_state(3)
    assert precheck(state, "fighter", "I cast a glance at the web of ropes") is None
    assert precheck(state, "wizard", "I cast a quick misty step") is not None
