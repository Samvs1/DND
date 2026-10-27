"""The read-line record (M43.1) and rule B1, on a real hero from a round-7 save."""

from aidm.models.events import AnyEvent, event_adapter
from aidm.models.impossible import ActionImpossible, LineRead
from aidm.models.state import GameState
from aidm.models.world_events import NarrationRecorded
from aidm.session.reducer import apply, replay
from scripts.contractlib.line_rules import LineOutcomes, named_things
from scripts.contractlib.save import Finding, walk
from tests.unit.contract.helpers import fixture

SAVE = "m39-r7-quests"


def _state() -> GameState:
    return walk(fixture(SAVE), [])[0]


def _talk() -> NarrationRecorded:
    return next(e.event for e in fixture(SAVE).events if isinstance(e.event, NarrationRecorded))


def _play(state: GameState, line: str, *after: AnyEvent) -> list[Finding]:
    rule = LineOutcomes()
    read = LineRead(creature_id="pc-p4", text=line, steps=(), other=True)
    found = rule.see(10, state, read)
    for i, event in enumerate(after):
        found += rule.see(11 + i, state, event)
    return found + rule.end(state)


def test_contract_line_read_round_trips_and_replays() -> None:
    read = LineRead(
        creature_id="pc-p4", text="I cast sacred flame", steps=("cast:sacred-flame>g1",)
    )
    assert event_adapter.validate_python(event_adapter.dump_python(read)) == read
    state = _state()
    before = state.model_copy(deep=True)
    apply(state, read)
    assert state.event_count == before.event_count + 1
    assert replay(before, [read]).model_dump() == state.model_dump()


def test_contract_old_saves_have_no_line_read_and_replay() -> None:
    events = [e.event for e in fixture(SAVE).events]
    assert not any(isinstance(e, LineRead) for e in events)


def test_contract_named_things_finds_a_known_spell_and_gold() -> None:
    state = _state()
    assert "sacred-flame" in named_things(state, "pc-p4", "I cast sacred flame at the goblin")
    assert "50 gold" in named_things(state, "pc-p4", "I hand over 50 gold")
    assert named_things(state, "pc-p4", "I stare at the sky and sigh") == []


def test_contract_b1_a_line_naming_a_spell_answered_by_talk_only_is_found() -> None:
    found = _play(_state(), "I cast sacred flame at the goblin", _talk())
    assert [f.rule for f in found] == ["B1"] and found[0].idx == 10


def test_contract_b1_a_line_with_a_refusal_passes() -> None:
    refusal = ActionImpossible(creature_id="pc-p4", text="x", reason="out of reach")
    assert _play(_state(), "I cast sacred flame at the goblin", refusal, _talk()) == []


def test_contract_b1_flavour_naming_no_game_thing_passes() -> None:
    assert _play(_state(), "I stare at the sky and sigh", _talk()) == []
