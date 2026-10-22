"""PlaceLit in the reducer (M27.2): set, cleared by PartyMoved, replay == snapshot, old saves."""

import json

import pytest

from aidm.models.events import AnyEvent, LoggedEvent, event_adapter
from aidm.models.state import GameState
from aidm.models.world import PlaceLight
from aidm.models.world_events import PartyMoved, PlaceLit
from aidm.session.persistence import replay_log
from aidm.session.reducer import apply, replay
from aidm.session.reducer_errors import ReducerError
from tests.unit.rules.encounter_fixtures import make_pc


def _base() -> GameState:
    state = GameState(campaign_id="lit", seed=1)
    state.creatures["hero"] = make_pc("hero")
    return state


def _events() -> list[AnyEvent]:
    return [
        PartyMoved(from_node=None, to_node="cave", scene_index=1),
        PlaceLit(node="cave", by="hero", reach="zone"),
    ]


def test_place_lit_is_set_and_cleared_on_party_moved() -> None:
    state = replay(_base(), _events())
    assert state.world.lit == PlaceLight(node="cave", by="hero", reach="zone")
    apply(state, PartyMoved(from_node="cave", to_node="crypt", scene_index=2))
    assert state.world.lit is None


def test_place_lit_needs_a_known_bearer() -> None:
    with pytest.raises(ReducerError):
        apply(GameState(campaign_id="lit", seed=1), PlaceLit(node="cave", by="ghost"))


def test_replay_with_place_lit_equals_snapshot() -> None:
    base = _base()
    live = base.model_copy(deep=True)
    for event in _events():
        apply(live, event)
    log = [
        LoggedEvent(seq=i, event=event_adapter.validate_json(event.model_dump_json()))
        for i, event in enumerate(_events())
    ]
    snapshot = GameState.model_validate_json(live.model_dump_json())
    assert replay_log(base, log) == snapshot == live


def test_old_save_without_light_loads_and_replays() -> None:
    raw = json.loads(_base().model_dump_json())
    raw["world"].pop("lit")  # a save from before M27.2
    old = GameState.model_validate(raw)
    assert old.world.lit is None
    log = [LoggedEvent(seq=0, event=PartyMoved(from_node=None, to_node="cave", scene_index=1))]
    assert replay_log(old, log).world.current_node == "cave"
