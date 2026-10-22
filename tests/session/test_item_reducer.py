"""Item-use events in the reducer (M27.3): boons, alert, charges, foraging, charting; PartyMoved
clears the place-scoped ones; replay == snapshot; saves from before M27.3 load and replay."""

import json

import pytest

from aidm.models.character import InventoryItem
from aidm.models.events import AnyEvent, InventoryChanged, LoggedEvent, event_adapter
from aidm.models.item_events import (
    BoonEnded,
    BoonGained,
    ItemUsed,
    ItemUseRefused,
    PlaceAlerted,
    PlacesCharted,
)
from aidm.models.state import GameState
from aidm.models.world import ActiveBoon
from aidm.models.world_events import PartyMoved
from aidm.session.persistence import replay_log
from aidm.session.reducer import apply, replay
from aidm.session.reducer_errors import ReducerError
from tests.unit.rules.encounter_fixtures import make_pc

HERE = "cave"
GLASS = ActiveBoon(
    creature_id="hero",
    use_id="glass",
    name="Magnifying glass",
    skills=("investigation",),
    node=HERE,
)
ANTITOXIN = ActiveBoon(
    creature_id="hero",
    use_id="antitoxin",
    name="Antitoxin",
    saves_against=("poison",),
    scope="until_long_rest",
)


def _base() -> GameState:
    state = GameState(campaign_id="items", seed=1)
    state.creatures["hero"] = make_pc("hero")
    pc = state.creatures["hero"].pc
    assert pc is not None
    pc.inventory = [InventoryItem(item="healers-kit", qty=2)]
    return state


def _events() -> list[AnyEvent]:
    return [
        PartyMoved(from_node=None, to_node=HERE, scene_index=1),
        ItemUsed(
            creature_id="hero",
            item="healers-kit",
            use_id="healers-kit-stabilize",
            target="ally",
            node=HERE,
            spends_charge=True,
            charges_left=9,
        ),
        ItemUsed(creature_id="hero", item="healers-kit", use_id="fish", node=HERE, forage=True),
        ItemUseRefused(creature_id="hero", item="torch", message="It is not dark here."),
        BoonGained(boon=GLASS),
        BoonGained(boon=ANTITOXIN),
        PlaceAlerted(node=HERE),
        PlacesCharted(nodes=("crypt", "marsh")),
        InventoryChanged(creature_id="hero", item="healers-kit", delta=1, qty=3),
    ]


def test_item_events_set_the_world_and_the_inventory() -> None:
    state = replay(_base(), _events())
    world = state.world
    assert world.boons == [GLASS, ANTITOXIN]
    assert (world.alerted, world.foraged, world.charted) == (HERE, [HERE], ["crypt", "marsh"])
    pc = state.creatures["hero"].pc
    assert pc is not None
    assert (pc.inventory[0].qty, pc.inventory[0].charges) == (3, 9)  # a stack change keeps charges


def test_party_moved_clears_the_alert_and_place_boons_only() -> None:
    state = replay(_base(), _events())
    apply(state, PartyMoved(from_node=HERE, to_node="crypt", scene_index=2))
    assert state.world.alerted is None
    assert state.world.boons == [ANTITOXIN]
    assert state.world.foraged == [HERE]  # once per place, for good


def test_boon_ended_and_regained_boons() -> None:
    state = replay(_base(), _events())
    apply(state, BoonGained(boon=GLASS.model_copy(update={"name": "Glass"})))
    assert [b.name for b in state.world.boons] == ["Antitoxin", "Glass"]
    apply(state, BoonEnded(creature_id="hero", use_id="antitoxin", reason="long rest"))
    assert [b.use_id for b in state.world.boons] == ["glass"]


def test_bad_item_events_raise() -> None:
    with pytest.raises(ReducerError):
        apply(_base(), ItemUsed(creature_id="ghost", item="torch", use_id="torch-light"))
    with pytest.raises(ReducerError):
        apply(
            _base(),
            ItemUsed(creature_id="hero", item="torch", use_id="t", spends_charge=True),
        )
    with pytest.raises(ReducerError):
        apply(_base(), BoonGained(boon=GLASS.model_copy(update={"creature_id": "ghost"})))


def test_replay_with_item_events_equals_snapshot() -> None:
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


def test_old_save_without_gear_fields_loads_and_replays() -> None:
    raw = json.loads(_base().model_dump_json())
    for key in ("boons", "alerted", "foraged", "charted"):
        raw["world"].pop(key)  # a save from before M27.3
    old = GameState.model_validate(raw)
    assert (old.world.boons, old.world.alerted, old.world.charted) == ([], None, [])
    log = [LoggedEvent(seq=i, event=e) for i, e in enumerate(_events())]
    assert replay_log(old, log).world.alerted == HERE
