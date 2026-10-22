"""Carried light in the reducer (M27.12): LightLit / LightEnded, kept on PartyMoved, replay ==
snapshot, and snapshots from M27.2-M27.3 (place-bound `"lit": null`) still load."""

import json

import pytest

from aidm.models.events import AnyEvent, LoggedEvent, event_adapter
from aidm.models.item_events import LightEnded, LightLit, PlaceAlerted
from aidm.models.state import GameState
from aidm.models.world import CarriedLight
from aidm.models.world_events import PartyMoved
from aidm.session.persistence import replay_log
from aidm.session.reducer import apply, replay
from aidm.session.reducer_errors import ReducerError
from tests.unit.rules.encounter_fixtures import make_pc


def _base() -> GameState:
    state = GameState(campaign_id="lit", seed=1)
    state.creatures["hero"] = make_pc("hero")
    state.creatures["ally"] = make_pc("ally")
    return state


def _events() -> list[AnyEvent]:
    return [
        PartyMoved(from_node=None, to_node="cave", scene_index=1),
        LightLit(creature_id="hero", item="candle", reach="zone"),
        LightLit(creature_id="ally", item="torch"),
        PartyMoved(from_node="cave", to_node="crypt", scene_index=2),
        PlaceAlerted(node="crypt"),
        LightEnded(creature_id="ally", reason="long rest"),
    ]


def test_carried_lights_travel_and_end_one_by_one() -> None:
    state = replay(_base(), _events()[:4])
    assert state.world.lights == [
        CarriedLight(creature_id="hero", item="candle", reach="zone"),
        CarriedLight(creature_id="ally", item="torch", reach="touching"),
    ]
    apply(state, LightEnded(creature_id="ally", reason="long rest"))
    assert [x.creature_id for x in state.world.lights] == ["hero"]


def test_one_light_per_hero() -> None:
    state = replay(_base(), _events()[:2])
    apply(state, LightLit(creature_id="hero", item="lantern-hooded"))
    assert state.world.lights == [CarriedLight(creature_id="hero", item="lantern-hooded")]


def test_light_lit_needs_a_known_bearer() -> None:
    with pytest.raises(ReducerError):
        apply(GameState(campaign_id="lit", seed=1), LightLit(creature_id="ghost", item="torch"))


def test_replay_with_carried_light_equals_snapshot() -> None:
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
    assert [x.creature_id for x in snapshot.world.lights] == ["hero"]
    assert snapshot.world.alerted == "crypt"


def test_old_snapshot_with_place_lit_null_loads_and_replays() -> None:
    raw = json.loads(_base().model_dump_json())
    raw["world"].pop("lights")
    raw["world"]["lit"] = None  # a snapshot written by M27.2-M27.3
    old = GameState.model_validate_json(json.dumps(raw))
    assert old.world.lights == []
    log = [LoggedEvent(seq=0, event=LightLit(creature_id="hero", item="torch"))]
    assert replay_log(old, log).world.lights == [CarriedLight(creature_id="hero", item="torch")]


def test_old_save_without_light_loads() -> None:
    raw = json.loads(_base().model_dump_json())
    raw["world"].pop("lights")  # a save from before M27.2
    old = GameState.model_validate(raw)
    assert old.world.lights == []
    log = [LoggedEvent(seq=0, event=PartyMoved(from_node=None, to_node="cave", scene_index=1))]
    assert replay_log(old, log).world.current_node == "cave"
