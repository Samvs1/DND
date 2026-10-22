"""M27.7: reading a spell scroll (anyone, an action, no slot), SRD 5.1 Spell Scroll numbers."""

from __future__ import annotations

import random
from dataclasses import replace

from aidm.data.combat_data import combat_registries
from aidm.data.registry import Registry
from aidm.models.character import InventoryItem
from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.encounter import Side
from aidm.models.encounter_events import EconomyChanged
from aidm.models.events import CheckResolved
from aidm.models.item_events import ItemUsed
from aidm.models.state import GameState
from aidm.rules.gear_menu import fight_gear_lines
from aidm.rules.item_use import use_item
from aidm.rules.opening_strike import opening_strike
from aidm.rules.scroll_read import scroll_numbers
from tests.unit.rules.combat_fixtures import economy, monster
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.item_fixtures import CAVE, DOCKS, at, gear_fight, hero, qty, refusal, run, use

REGS = combat_registries()


def _fight(gear: list[str], hp: int = 10) -> GameState:
    return gear_fight(CAVE, hero(gear=gear), (monster("gob", hp=hp), Side.HOSTILE, "b"))


def test_golden_scroll_numbers_follow_the_srd_table() -> None:
    # SRD 5.1 Spell Scroll: 1st level save DC 13, attack +5; 3rd level save DC 15, attack +7.
    one, three = scroll_numbers(1), scroll_numbers(3)
    assert (one.save_dc, one.attack_bonus, one.modifier) == (13, 5, 3)
    assert (three.save_dc, three.attack_bonus) == (15, 7)


def test_golden_level1_save_scroll_uses_dc_13_not_the_readers() -> None:
    # A fighter (no spellcasting at all) reads Hideous Laughter (1st level, WIS save): DC 13.
    state = _fight(["scroll-of-hideous-laughter"])
    events = use(state, "scroll-of-hideous-laughter", "gob")
    saves = [e for e in events if isinstance(e, CheckResolved)]
    assert saves and saves[0].result.dc == 13 and saves[0].creature_id == "gob"
    assert isinstance(events[0], EconomyChanged) and not events[0].economy.action
    assert [e.spell_id for e in events if isinstance(e, SpellCast)] == ["hideous-laughter"]
    run(state, events)
    assert qty(state, "hero", "scroll-of-hideous-laughter") == 0
    assert not economy(state, "hero").action


def test_golden_level3_attack_scroll_uses_plus_7() -> None:
    # SRD 5.1 Spell Scroll: a 3rd-level scroll attacks at +7. No shipped 3rd-level spell rolls
    # to hit, so Guiding Bolt's data is read as a 3rd-level scroll.
    bolt = REGS.spells.get("guiding-bolt").model_copy(update={"level": 3})
    spells = Registry([bolt if s.index == bolt.index else s for s in REGS.spells.all()])
    state = _fight(["scroll-of-guiding-bolt"])
    rng = random.Random(4)
    events = use_item(
        state, "hero", "scroll-of-guiding-bolt", "gob", rng=rng, regs=replace(REGS, spells=spells)
    )
    rolled = next(e for e in events if isinstance(e, AttackRolled))
    assert rolled.roll.total - rolled.roll.natural == 7


def test_a_wizard_reads_a_scroll_without_spending_a_slot() -> None:
    wizard = make_pc("hero", class_index="wizard")
    assert wizard.pc is not None
    wizard.pc.inventory.append(InventoryItem(item="scroll-of-magic-missile", qty=1))
    state = gear_fight(CAVE, wizard, (monster("gob", hp=30), Side.HOSTILE, "b"))
    slots = state.creatures["hero"].resources["spell-slot-1"].current
    run(state, use(state, "scroll-of-magic-missile", "gob"))
    assert state.creatures["hero"].resources["spell-slot-1"].current == slots
    assert state.creatures["gob"].hp < 30
    assert qty(state, "hero", "scroll-of-magic-missile") == 0


def test_sleep_read_at_a_foe_lands_in_its_zone() -> None:
    state = _fight(["scroll-of-sleep"], hp=5)
    events = use(state, "scroll-of-sleep", "gob", rng=random.Random(1))
    cast = next(e for e in events if isinstance(e, SpellCast))
    assert cast.target_zone == "b"
    run(state, events)
    assert any(c.name == "asleep" for c in state.creatures["gob"].conditions)


def test_an_engine_refusal_spends_nothing() -> None:
    state = _fight(["scroll-of-sleep"])
    message = refusal(use(state, "scroll-of-sleep"))  # an area spell needs an area
    assert "area" in message.lower()
    assert qty(state, "hero", "scroll-of-sleep") == 1 and economy(state, "hero").action


def test_out_of_a_fight_a_harmful_scroll_at_no_one_is_spent_with_no_effect() -> None:
    state = at(DOCKS, hero(gear=["scroll-of-fireball"]))
    events = use(state, "scroll-of-fireball")
    used = events[0]
    assert isinstance(used, ItemUsed) and used.no_effect
    run(state, events)
    assert qty(state, "hero", "scroll-of-fireball") == 0


def test_out_of_a_fight_a_harmful_scroll_at_someone_starts_the_fight_first() -> None:
    state = at(DOCKS, hero(gear=["scroll-of-fire-bolt"]), hero("ally"))
    message = refusal(use(state, "scroll-of-fire-bolt", "ally"))
    assert "start_encounter" in message and "'scroll-of-fire-bolt'" in message
    npc = next(iter(state.world.npcs.values()))
    assert npc.name in refusal(use(state, "scroll-of-fire-bolt", npc.id))
    assert qty(state, "hero", "scroll-of-fire-bolt") == 1


def test_out_of_a_fight_a_healing_scroll_read_at_no_one_heals_the_reader() -> None:
    me = hero(gear=["scroll-of-cure-wounds"])
    me.hp = 1
    state = at(DOCKS, me)
    run(state, use(state, "scroll-of-cure-wounds", rng=random.Random(2)))
    assert state.creatures["hero"].hp >= 1 + 1 + 3  # 1d8 + 3 (the scroll's modifier)
    assert qty(state, "hero", "scroll-of-cure-wounds") == 0


def test_a_scroll_named_as_the_opening_strike_is_read_with_no_action_spent() -> None:
    state = _fight(["scroll-of-fire-bolt"])
    events = opening_strike(state, "hero", "gob", REGS, random.Random(2), "scroll-of-fire-bolt")
    assert not any(isinstance(e, EconomyChanged) for e in events)
    assert any(isinstance(e, AttackRolled) for e in events)
    run(state, events)
    assert qty(state, "hero", "scroll-of-fire-bolt") == 0 and economy(state, "hero").action
    # The scroll is gone now: a refused read rolls nothing (no weapon in its place).
    assert opening_strike(state, "hero", "gob", REGS, random.Random(2), "scroll-of-fire-bolt") == []


def test_scrolls_join_the_hotbar_items_with_their_action_cost() -> None:
    gear = ["scroll-of-sleep", "scroll-of-cure-wounds", "scroll-of-burning-hands"]
    lines = {line.item: line for line in fight_gear_lines(hero(gear=gear))}
    assert {line.cost for line in lines.values()} == {"action"}
    assert lines["scroll-of-sleep"].target == "zone"
    assert lines["scroll-of-cure-wounds"].target == "creature"
    assert lines["scroll-of-burning-hands"].target == "none"
    assert lines["scroll-of-sleep"].name == "Scroll of Sleep"
