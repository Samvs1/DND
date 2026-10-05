"""The spell-slot model and spellcasting numbers (SPEC 7.2, 8).

Goldens cite the SRD 5.1 class tables (Spell Slots per Spell Level, Pact Magic) and the
Spellcasting features (save DC = 8 + proficiency bonus + modifier; attack = PB + modifier;
prepared = modifier + level, minimum 1).
"""

from __future__ import annotations

import pytest

from aidm.data.character_data import character_registries
from aidm.models.abilities import Ability
from aidm.models.events import AnyEvent, CreatureAdded, ResourceRemoved, ResourceSet
from aidm.models.state import Creature, CreatureKind, GameState, RechargeKind
from aidm.rules.creation import build_character, validate_creation
from aidm.rules.rests import long_rest, short_rest
from aidm.rules.spellcasting import (
    SlotError,
    SlotKind,
    SlotRef,
    can_cast,
    cantrips_known_count,
    choose_slot,
    class_slot_maximums,
    max_spell_level,
    parse_slot_key,
    prepared_spell_limit,
    slot_key,
    slot_maximum_events,
    slot_resources,
    spell_attack_bonus,
    spell_save_dc,
    spellcasting_ability,
    spells_known_count,
    spend_slot,
)
from aidm.session.reducer import apply
from tests.unit.rules.creation_fixtures import default_choices

CLASSES = character_registries().classes


def _slots(cls: str, level: int) -> dict[str, int]:
    return class_slot_maximums(CLASSES.get(cls), level)


def test_golden_wizard_and_cleric_slots() -> None:
    # SRD 5.1 Wizard/Cleric tables: 2 / 3 / 4-2 / 4-3 / 4-3-2 for levels 1-5.
    expected = [
        {"spell-slot-1": 2},
        {"spell-slot-1": 3},
        {"spell-slot-1": 4, "spell-slot-2": 2},
        {"spell-slot-1": 4, "spell-slot-2": 3},
        {"spell-slot-1": 4, "spell-slot-2": 3, "spell-slot-3": 2},
    ]
    for cls in ("wizard", "cleric"):
        assert [_slots(cls, lvl) for lvl in range(1, 6)] == expected


def test_golden_warlock_pact_slots() -> None:
    # SRD 5.1 Warlock Pact Magic: 1 slot (lvl 1), 2 (lvl 1), 2 (lvl 2), 2 (lvl 2), 2 (lvl 3).
    expected = [
        {"pact-slot-1": 1},
        {"pact-slot-1": 2},
        {"pact-slot-2": 2},
        {"pact-slot-2": 2},
        {"pact-slot-3": 2},
    ]
    assert [_slots("warlock", lvl) for lvl in range(1, 6)] == expected
    pools = slot_resources(CLASSES.get("warlock"), 5)
    assert pools["pact-slot-3"].recharge is RechargeKind.SHORT_REST


def test_golden_ranger_and_martial_slots() -> None:
    # SRD 5.1 Ranger (half caster from level 2): 0 / 2 / 3 / 3 / 4-2.
    assert [_slots("ranger", lvl) for lvl in range(1, 6)] == [
        {},
        {"spell-slot-1": 2},
        {"spell-slot-1": 3},
        {"spell-slot-1": 3},
        {"spell-slot-1": 4, "spell-slot-2": 2},
    ]
    for cls in ("fighter", "rogue"):
        assert all(_slots(cls, lvl) == {} for lvl in range(1, 6))
    assert slot_resources(CLASSES.get("wizard"), 1)["spell-slot-1"].recharge is (
        RechargeKind.LONG_REST
    )


def test_golden_known_counts() -> None:
    # SRD 5.1: warlock cantrips 2,2,2,3,3 and spells known 2..6; wizard cantrips 3,3,3,4,4.
    warlock, wizard = CLASSES.get("warlock"), CLASSES.get("wizard")
    assert [cantrips_known_count(warlock, lvl) for lvl in range(1, 6)] == [2, 2, 2, 3, 3]
    assert [spells_known_count(warlock, lvl) for lvl in range(1, 6)] == [2, 3, 4, 5, 6]
    assert [cantrips_known_count(wizard, lvl) for lvl in range(1, 6)] == [3, 3, 3, 4, 4]
    assert spells_known_count(wizard, 3) == 0
    assert [max_spell_level(CLASSES.get("ranger"), lvl) for lvl in range(1, 6)] == [0, 1, 1, 1, 2]


def test_golden_prepared_limit() -> None:
    # SRD 5.1 Cleric/Wizard: ability modifier + level, minimum 1.
    cleric = CLASSES.get("cleric")
    wis16 = dict.fromkeys(Ability, 10) | {Ability.WIS: 16}
    assert prepared_spell_limit(cleric, 1, wis16) == 4
    assert prepared_spell_limit(cleric, 5, wis16) == 8
    assert prepared_spell_limit(cleric, 1, dict.fromkeys(Ability, 8)) == 1
    assert prepared_spell_limit(CLASSES.get("warlock"), 3, wis16) == 0
    assert prepared_spell_limit(CLASSES.get("fighter"), 3, wis16) == 0


def _pc(cls: str, race: str = "human", sub: str | None = None, **scores: int) -> Creature:
    choices = default_choices(cls, race, sub)
    if scores:
        base = dict(choices.base_scores) | {Ability(k): v for k, v in scores.items()}
        choices = choices.model_copy(update={"base_scores": base})
    return build_character(choices, character_registries(), f"{cls}1")


def test_golden_dc_and_attack_sample_builds() -> None:
    # Human wizard, standard array INT 15 (+1 human) = 16 -> +3; PB 2: DC 13, attack +5.
    wizard = _pc("wizard", str=12, int=15)
    wiz = CLASSES.get("wizard")
    assert (spell_save_dc(wizard, wiz), spell_attack_bonus(wizard, wiz)) == (13, 5)
    # Tiefling warlock CHA 15 + 2 = 17 -> +3: DC 13, attack +5.
    warlock = _pc("warlock", "tiefling", cha=15, str=8)
    war = CLASSES.get("warlock")
    assert (spell_save_dc(warlock, war), spell_attack_bonus(warlock, war)) == (13, 5)
    # Level 5 wizard with INT 18 (+4) and PB 3: DC 15, attack +7.
    sage = wizard.model_copy(update={"proficiency_bonus": 3})
    sage.abilities[Ability.INT] = 18
    assert (spell_save_dc(sage, wiz), spell_attack_bonus(sage, wiz)) == (15, 7)
    assert spellcasting_ability(CLASSES.get("cleric")) is Ability.WIS
    with pytest.raises(ValueError):
        spellcasting_ability(CLASSES.get("fighter"))


def test_creation_sets_slots_and_prepared_limit() -> None:
    wizard = _pc("wizard")
    assert wizard.resources["spell-slot-1"].current == 2
    assert "pact-slot-1" in _pc("warlock").resources
    assert not any(parse_slot_key(k) for k in _pc("ranger").resources)
    choices = default_choices("cleric", "human", None)
    regs = character_registries()
    too_many = choices.model_copy(
        update={"prepared": ["bless", "cure-wounds", "bane", "guiding-bolt"]}
    )
    # Cleric WIS: standard array 10 (+1 human) = 11 -> +0, level 1: limit 1.
    codes = [e.code.value for e in validate_creation(too_many, regs)]
    assert codes == ["prepared_over_limit"]


def test_slot_keys_round_trip() -> None:
    assert slot_key(SlotKind.PACT, 3) == "pact-slot-3"
    assert parse_slot_key("spell-slot-9") == SlotRef(level=9, kind=SlotKind.STANDARD)
    for bad in ("rage", "spell-slot-0", "spell-slot-10", "pact-slot-x", "slot-1"):
        assert parse_slot_key(bad) is None
    with pytest.raises(ValueError):
        slot_key(SlotKind.STANDARD, 0)


def _apply_all(state: GameState, events: list[AnyEvent]) -> None:
    for event in events:
        apply(state, event)


def _state(pc: Creature) -> GameState:
    state = GameState(campaign_id="c", seed=1, camp_supplies=100)
    apply(state, _added(pc))
    return state


def _added(pc: Creature) -> AnyEvent:
    return CreatureAdded(creature=pc)


def test_spend_lowest_and_upcast() -> None:
    state = _state(_pc("wizard"))
    _apply_all(state, slot_maximum_events(state.creatures["wizard1"], CLASSES.get("wizard"), 5))
    pc = state.creatures["wizard1"]
    assert choose_slot(pc, 1) == SlotRef(level=1, kind=SlotKind.STANDARD)
    assert choose_slot(pc, 1, 3) == SlotRef(level=3, kind=SlotKind.STANDARD)
    events = spend_slot(pc, 2, 3)
    assert isinstance(events[0], ResourceSet) and events[0].key == "spell-slot-3"
    with pytest.raises(SlotError):
        choose_slot(pc, 3, 2)
    with pytest.raises(SlotError):
        choose_slot(pc, 4)
    assert spend_slot(pc, 0) == [] and can_cast(pc, 0)
    assert not can_cast(pc, 0, 1)
    for _ in range(2):
        _apply_all(state, spend_slot(state.creatures["wizard1"], 3))
    pc = state.creatures["wizard1"]
    assert not can_cast(pc, 3) and can_cast(pc, 2) and can_cast(pc, 1, 2)
    with pytest.raises(SlotError):
        spend_slot(pc, 3)


def test_pact_slot_always_at_pact_level() -> None:
    state = _state(_pc("warlock"))
    warlock_def = CLASSES.get("warlock")
    _apply_all(state, slot_maximum_events(state.creatures["warlock1"], warlock_def, 5))
    pc = state.creatures["warlock1"]
    assert choose_slot(pc, 1) == SlotRef(level=3, kind=SlotKind.PACT)
    assert not can_cast(pc, 1, 1) and can_cast(pc, 1, 3) and not can_cast(pc, 4)
    _apply_all(state, spend_slot(pc, 1))
    assert state.creatures["warlock1"].resources["pact-slot-3"].current == 1


def test_level_up_moves_pact_pool_and_keeps_spent() -> None:
    state = _state(_pc("warlock"))
    warlock_def = CLASSES.get("warlock")
    _apply_all(state, slot_maximum_events(state.creatures["warlock1"], warlock_def, 2))
    _apply_all(state, spend_slot(state.creatures["warlock1"], 1))
    events = slot_maximum_events(state.creatures["warlock1"], warlock_def, 3)
    assert ResourceRemoved(creature_id="warlock1", key="pact-slot-1") in events
    _apply_all(state, events)
    pools = state.creatures["warlock1"].resources
    assert "pact-slot-1" not in pools and pools["pact-slot-2"].current == 1
    assert slot_maximum_events(state.creatures["warlock1"], warlock_def, 3) == []


def test_rests_restore_the_right_kinds() -> None:
    state = _state(_pc("wizard"))
    apply(state, _added(_pc("warlock")))
    _apply_all(state, spend_slot(state.creatures["wizard1"], 1))
    _apply_all(state, spend_slot(state.creatures["warlock1"], 1))
    _apply_all(state, short_rest(state))
    assert state.creatures["warlock1"].resources["pact-slot-1"].current == 1
    assert state.creatures["wizard1"].resources["spell-slot-1"].current == 1
    _apply_all(state, long_rest(state))
    assert state.creatures["wizard1"].resources["spell-slot-1"].current == 2
    assert state.creatures["wizard1"].kind is CreatureKind.PC
