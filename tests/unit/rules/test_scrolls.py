"""Wizard scroll copying (BG3: gold per spell level, scroll consumed; SRD 50 gp per level)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from aidm.data.character_data import character_registries
from aidm.models.events import (
    AnyEvent,
    CreatureAdded,
    GoldChanged,
    InventoryChanged,
    SpellbookChanged,
    XpGained,
)
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.creation import build_character
from aidm.rules.scrolls import (
    ScrollCopyRefusal,
    ScrollCopyRefused,
    copy_scroll_to_spellbook,
    scroll_copy_lines,
    scroll_item_index,
    scroll_spell_index,
)
from aidm.session.reducer import ReducerError, apply, replay
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.leveling_fixtures import level_to

REGS = character_registries()
R = ScrollCopyRefusal
SCROLLS = ("magic-missile", "fire-bolt", "misty-step", "cure-wounds", "alarm", "shield")
SCROLLS += ("burning-hands",)


def _state(cls: str = "wizard", gold: int = 100, level: int = 1) -> GameState:
    pc = build_character(default_choices(cls, "elf", "high-elf"), REGS, "w")
    state = apply(GameState(campaign_id="c", seed=1), CreatureAdded(creature=pc))
    level_to(state, "w", level, REGS, [])
    events: list[AnyEvent] = [GoldChanged(creature_id="w", delta=gold, gold=gold)]
    events += [
        InventoryChanged(creature_id="w", item=scroll_item_index(s), delta=1, qty=1)
        for s in SCROLLS
    ]
    for event in events:
        apply(state, event)
    return state


def _refusal(wizard: Creature, spell: str) -> ScrollCopyRefusal:
    with pytest.raises(ScrollCopyRefused) as info:
        copy_scroll_to_spellbook(wizard, scroll_item_index(spell), REGS)
    return info.value.reason


def _run(state: GameState, events: Sequence[AnyEvent]) -> Creature:
    for event in events:
        apply(state, event)
    return state.creatures["w"]


def test_golden_copy_costs_fifty_per_level_and_consumes_scroll() -> None:
    state = _state()
    initial = state.model_copy(deep=True)
    events = copy_scroll_to_spellbook(state.creatures["w"], "scroll-of-magic-missile", REGS)
    assert [type(e) for e in events] == [GoldChanged, InventoryChanged, SpellbookChanged]
    wizard = _run(state, events)
    assert wizard.pc is not None
    assert wizard.pc.gold == 50  # 1st-level spell: 50 gold
    assert "magic-missile" in wizard.pc.spellbook
    assert "scroll-of-magic-missile" not in [row.item for row in wizard.pc.inventory]
    assert replay(initial, events) == state


def test_golden_evocation_savant_halves_cost() -> None:
    state = _state(level=2)
    events = copy_scroll_to_spellbook(state.creatures["w"], "scroll-of-magic-missile", REGS)
    assert events[0] == GoldChanged(creature_id="w", delta=-25, gold=75)


def test_refusals_change_nothing() -> None:
    wizard = _state(gold=40).creatures["w"]
    assert _refusal(wizard, "magic-missile") is R.NOT_ENOUGH_GOLD
    rich = _state().creatures["w"]
    assert _refusal(rich, "fire-bolt") is R.CANTRIP
    assert _refusal(rich, "misty-step") is R.LEVEL_TOO_HIGH
    assert _refusal(rich, "cure-wounds") is R.NOT_CLASS_SPELL
    assert _refusal(rich, "burning-hands") is R.ALREADY_KNOWN
    assert _refusal(rich, "alarm") is R.NOT_CLASS_SPELL  # M3.6b: unshipped spells are not learnable
    assert _refusal(rich, "sleep") is R.NO_SCROLL
    fighter = _state("fighter").creatures["w"]
    assert _refusal(fighter, "shield") is R.NO_SCROLL_COPY
    monster = Creature(id="m", name="M", kind=CreatureKind.MONSTER, max_hp=1, hp=1)
    assert _refusal(monster, "shield") is R.NOT_A_PC


def test_unknown_scroll_spell() -> None:
    state = _state()
    apply(state, InventoryChanged(creature_id="w", item="scroll-of-nonsense", delta=1, qty=1))
    assert _refusal(state.creatures["w"], "nonsense") is R.UNKNOWN_SPELL
    assert scroll_spell_index("dagger") is None and scroll_spell_index("scroll-of-") is None


def test_inventory_and_pc_events_in_reducer() -> None:
    state = _state()
    wizard = _run(state, [InventoryChanged(creature_id="w", item="dagger", delta=-1, qty=0)])
    assert wizard.pc is not None and "dagger" not in [r.item for r in wizard.pc.inventory]
    wizard = _run(state, [InventoryChanged(creature_id="w", item="shield", delta=1, qty=1)])
    assert wizard.pc is not None and wizard.pc.inventory[-1].item == "shield"
    monster = Creature(id="m", name="M", kind=CreatureKind.MONSTER, max_hp=1, hp=1)
    apply(state, CreatureAdded(creature=monster))
    with pytest.raises(ReducerError):
        apply(state, XpGained(creature_id="m", amount=1, xp=1))


def test_golden_second_level_copy_costs_100_and_an_evocation_50() -> None:
    # SRD 5.1 Wizard "Your Spellbook": 50 gp per spell level (2nd level: 100 gp); Evocation
    # Savant (SRD 5.1 School of Evocation): copying an evocation spell costs half (50 gp).
    state = _state(level=3, gold=200)
    apply(state, InventoryChanged(creature_id="w", item="scroll-of-scorching-ray", delta=1, qty=1))
    misty = copy_scroll_to_spellbook(state.creatures["w"], "scroll-of-misty-step", REGS)
    assert misty[0] == GoldChanged(creature_id="w", delta=-100, gold=100)  # conjuration
    _run(state, misty)
    ray = copy_scroll_to_spellbook(state.creatures["w"], "scroll-of-scorching-ray", REGS)
    assert ray[0] == GoldChanged(creature_id="w", delta=-50, gold=50)  # evocation
    wizard = _run(state, ray)
    assert wizard.pc is not None and {"misty-step", "scorching-ray"} <= set(wizard.pc.spellbook)


def test_scroll_copy_lines_list_what_can_be_copied_with_its_cost() -> None:
    lines = scroll_copy_lines(_state(gold=40).creatures["w"], REGS)
    assert [(line.spell, line.cost, line.affordable) for line in lines] == [
        ("magic-missile", 50, False)  # cantrip, too high, not a wizard spell, known: left out
    ]
    assert scroll_copy_lines(_state("fighter").creatures["w"], REGS) == []
