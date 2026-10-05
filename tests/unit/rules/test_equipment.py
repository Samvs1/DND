"""Equip, unequip and drop (M6.2): slots, armour class deltas, refusals, replay."""

import pytest

from aidm.data.character_data import character_registries
from aidm.models.abilities import Ability
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.state import GameState
from aidm.models.world_events import EquipmentChanged, ItemPlaced
from aidm.rules.abilities import ability_modifier
from aidm.rules.equipment import (
    EquipRefusal,
    EquipRefused,
    drop_events,
    equip_events,
    unequip_events,
)
from aidm.session.reducer import apply, replay
from tests.ai.tool_fixtures import party_state

CHARS = character_registries()


def _apply(state: GameState, events: list[AnyEvent], log: list[AnyEvent]) -> None:
    for event in events:
        apply(state, event)
    log.extend(events)


def test_golden_unequip_shield_and_armour_moves_ac() -> None:
    # SRD 5.1 Armor table: chain mail AC 16 (no Dex), shield +2; unarmoured AC = 10 + Dex mod.
    state, log = party_state(), []
    start = state.model_copy(deep=True)
    fighter = state.creatures["fighter"]
    assert fighter.ac == 18
    _apply(state, unequip_events(fighter, "shield", CHARS), log)
    assert state.creatures["fighter"].ac == 16
    _apply(state, unequip_events(state.creatures["fighter"], "chain-mail", CHARS), log)
    dex = ability_modifier(state.creatures["fighter"].abilities[Ability.DEX])
    assert state.creatures["fighter"].ac == 10 + dex
    _apply(state, equip_events(state.creatures["fighter"], "chain-mail", CHARS), log)
    _apply(state, equip_events(state.creatures["fighter"], "shield", CHARS), log)
    assert state.creatures["fighter"].ac == 18
    assert replay(start, log).model_dump() == state.model_dump()


def test_main_hand_rules_for_light_and_heavy_weapons() -> None:
    state = party_state()
    rogue = state.creatures["rogue"]
    assert rogue.pc is not None and rogue.pc.equipped.off_hand == "dagger"
    events = equip_events(rogue, "rapier", CHARS)
    changed = events[0]
    assert isinstance(changed, EquipmentChanged)
    assert changed.equipped.main_hand == "rapier" and changed.equipped.off_hand is None
    assert changed.ac == rogue.ac


def test_refusals_are_typed() -> None:
    state = party_state()
    fighter = state.creatures["fighter"]
    cases = [
        (lambda: equip_events(fighter, "greataxe", CHARS), EquipRefusal.NOT_CARRIED),
        (lambda: equip_events(fighter, "longsword", CHARS), EquipRefusal.ALREADY_EQUIPPED),
        (lambda: equip_events(fighter, "potion-of-healing", CHARS), EquipRefusal.NOT_EQUIPMENT),
        (lambda: unequip_events(fighter, "pouch", CHARS), EquipRefusal.NOT_EQUIPPED),
        (lambda: drop_events(state, fighter, "greataxe", CHARS), EquipRefusal.NOT_CARRIED),
    ]
    for make, reason in cases:
        with pytest.raises(EquipRefused) as caught:
            make()
        assert caught.value.reason is reason


def test_drop_unequips_the_last_copy_and_places_it_here() -> None:
    state, log = party_state(), []
    events = drop_events(state, state.creatures["fighter"], "longsword", CHARS)
    assert [type(e) for e in events] == [EquipmentChanged, InventoryChanged, ItemPlaced]
    _apply(state, events, log)
    fighter = state.creatures["fighter"]
    assert fighter.pc is not None and fighter.pc.equipped.main_hand is None
    assert all(row.item != "longsword" for row in fighter.pc.inventory)
    placed = events[-1]
    assert isinstance(placed, ItemPlaced) and placed.item.node_id == "town"
    assert placed.item.id in state.world.items
    potion = drop_events(state, fighter, "potion-of-healing", CHARS)
    assert [type(e) for e in potion] == [InventoryChanged, ItemPlaced]
