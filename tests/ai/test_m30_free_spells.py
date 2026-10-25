"""M30.2b: no free spells by typing, the model side (FakeLLM only).

A model `no_mechanics` answer can never produce a narrated spell cast:
- a typed cast of a spell the hero has ready is cast by the engine before the model is asked
  (the one intent router, `dm.cast_intent`), so the model's answer never decides it;
- a cast the router leaves to the model (a hostile spell with an NPC here) and the model answers
  with `no_mechanics` and a story of the spell working: THE guard flags the sentence
  (`UNCAST_SPELL`, `dm.guard_cast`), the one retry flags again, and the template tells only the
  engine's events;
- a cast at the scene reaches the narrator as a fact and a note built from the spell's data."""

from pathlib import Path

from aidm.dm.event_text import event_lines, event_notes
from aidm.dm.fake_llm import FakeStream, fake_tool_call
from aidm.dm.guard import check_prose
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narration_stream import NarrationSource
from aidm.dm.narrator import narrate
from aidm.models.combat_events import SpellCast
from aidm.models.events import AnyEvent, ResourceSet
from aidm.models.protocol_client import SubmitAction
from aidm.models.state import GameState
from aidm.models.world_events import NarrationRecorded
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import party_state
from tests.session.table_fixtures import assert_replays, join, menu_llm, pick, running
from tests.sim.sim_setup import build_party
from tests.unit.rules.item_fixtures import DOCKS, at

BLINK = "I cast misty step to reach the roof of the warehouse"
FREE_BLINK = "The wizard casts Misty Step and lands on the warehouse roof."


def _docks() -> GameState:
    state = at(DOCKS)
    build_party(state, 3)
    wizard = state.creatures["wizard"].pc
    assert wizard is not None
    wizard.spellbook.append("misty-step")
    wizard.prepared.append("misty-step")
    return state


async def test_m30_typed_cast_is_cast_before_the_model(tmp_path: Path) -> None:
    """The model would answer `no_mechanics` (FakeLLM's default whenever tools are offered); it is
    never asked: the engine casts the spell and spends the slot. M36.10a: the menu chooser's call
    is the only one with a tool (it picks the cast; the storyteller only tells it)."""
    client, fake = menu_llm(tmp_path, pick(("cast:misty-step", [], None)))
    async with running(client, _docks()) as (table, _):
        seat = await join(table, "Ann", "wizard")
        start = table.state.event_count
        seat.send(SubmitAction(text=BLINK))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
    assert [e.spell_id for e in events if isinstance(e, SpellCast)] == ["misty-step"]
    assert any(isinstance(e, ResourceSet) and e.key == "spell-slot-2" for e in events)
    told = [r for r in fake.requests if r.tool_choice != "choose_actions"]
    assert told and not any(r.tools for r in told)


async def test_m30_no_mechanics_never_casts_free(tmp_path: Path) -> None:
    """A cast left to the model (a hostile spell with Tobin here), answered `no_mechanics` and told
    as working twice: the template tells the events instead, and no spell happened."""
    free = FakeStream(("The wizard casts Fire Bolt and the crates beside Tobin burst alight.",))
    client, _ = fake_client(tmp_path, [fake_tool_call("no_mechanics", {}), free, free])
    async with running(client, _docks()) as (table, _):
        seat = await join(table, "Ann", "wizard")
        start = table.state.event_count
        seat.send(SubmitAction(text="I cast fire bolt at Tobin"))
        await table.settle()
        events: list[AnyEvent] = [e.event for e in table.log if e.seq >= start]
    assert not any(isinstance(e, SpellCast | ResourceSet) for e in events)
    told = " ".join(e.text for e in events if isinstance(e, NarrationRecorded))
    assert told and "Fire Bolt" not in told


def test_m30_guard_flags_a_cast_with_no_cast_event() -> None:
    state = _docks()
    report = check_prose(FREE_BLINK, state)
    assert [v.kind for v in report.violations] == [ViolationKind.UNCAST_SPELL]
    cast = SpellCast(caster_id="wizard", spell_id="misty-step", cast_level=2, at_scene=True)
    assert check_prose(FREE_BLINK, state, events=[cast]).ok
    for fine in (
        "The wizard does not cast Misty Step.",
        "The wizard tries to cast Misty Step, but no slot answers.",
        "Long shadows cast on the web of ropes.",
    ):
        assert check_prose(fine, state).ok, fine


async def test_m30_free_cast_narration_falls_back_to_the_template(tmp_path: Path) -> None:
    state = _docks()
    client, fake = fake_client(tmp_path, [FakeStream((FREE_BLINK,)), FakeStream((FREE_BLINK,))])
    stream = narrate(state, [], client)
    text = await stream.collect()
    assert "Misty Step" not in text
    assert stream.source is NarrationSource.TEMPLATE and stream.retried
    assert stream.reports[0].violations[0].kind is ViolationKind.UNCAST_SPELL
    assert len(fake.requests) == 2


def test_m30_scene_cast_reaches_the_narrator_from_the_event() -> None:
    state = party_state(3)
    name = state.creatures["wizard"].name
    cast = SpellCast(caster_id="wizard", spell_id="misty-step", cast_level=2, at_scene=True)
    assert event_lines(state, [cast]) == [
        f"{name} casts Misty Step (outside a fight: it carries no one to another place)."
    ]
    assert "no one moved to another place" in event_notes(state, [cast])[0]
    bolt = SpellCast(caster_id="wizard", spell_id="fire-bolt", at_scene=True)
    assert "strikes no one" in event_lines(state, [bolt])[0]
    # a cast with targets renders no line, as before: its effects tell it
    aimed = SpellCast(
        caster_id="wizard", spell_id="cure-wounds", cast_level=1, target_ids=("wizard",)
    )
    assert event_lines(state, [aimed]) == [] and event_notes(state, [aimed]) == []
