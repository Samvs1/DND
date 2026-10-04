"""Golden numbers for the shipped level 1 spells beyond the 10 reference spells (SRD 5.1).

Casters have their casting ability at 16 (+3) and proficiency +2: spell save DC 13, spell
attack +5. Rolls are scripted. Monsters have AC 13, 30 HP and all ability scores 10.
"""

from __future__ import annotations

from aidm.models.combat import AttackProfile
from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.events import CheckResolved, DamageTaken
from aidm.rules.conditions import condition_ac_bonus
from aidm.rules.hit_chance import hit_chance
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng
from tests.unit.rules.spell_fixtures import battle, cast, caster, conditions_of, of, slots_left

CLAW = AttackProfile(key="claw", name="Claw", attack_bonus=4)


def test_golden_spell_animal_friendship() -> None:
    # Animal Friendship (ranger, level 2): WIS save DC 13 or charmed for 24 hours (14400 rounds).
    ranger = caster("r", "ranger", spells=["animal-friendship"], level=2, slots={1: 2})
    state = battle(ranger, ("gob", "yard"))
    events = cast(state, "r", "animal-friendship", ScriptedRng(5), targets=["gob"])
    assert of(events, CheckResolved)[0].result.dc == 13
    charmed = state.creatures["gob"].conditions[0]
    assert charmed.name == "charmed" and charmed.rounds_left == 14400
    assert slots_left(state.creatures["r"], 1) == 1
    state = battle(
        caster("r", "ranger", spells=["animal-friendship"], level=2, slots={1: 2}), ("gob", "yard")
    )
    cast(state, "r", "animal-friendship", ScriptedRng(13), targets=["gob"])
    assert conditions_of(state, "gob") == []


def test_golden_spell_charm_person() -> None:
    # Charm Person: WIS save DC 13, charmed for 1 hour (600 rounds); +1 target per slot above 1.
    wiz = caster("w", "wizard", spells=["charm-person"], slots={2: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    events = cast(state, "w", "charm-person", ScriptedRng(5, 5), targets=["gob", "gob2"], slot=2)
    assert of(events, SpellCast)[0].cast_level == 2
    assert [conditions_of(state, g) for g in ("gob", "gob2")] == [["charmed"], ["charmed"]]
    assert state.creatures["gob"].conditions[0].rounds_left == 600
    state = battle(caster("w", "wizard", spells=["charm-person"], slots={1: 1}), ("gob", "yard"))
    cast(state, "w", "charm-person", ScriptedRng(14), targets=["gob"])
    assert conditions_of(state, "gob") == [] and slots_left(state.creatures["w"], 1) == 0


def test_golden_spell_false_life() -> None:
    # False Life: 1d4 + 4 temporary hit points; +5 per slot level above 1.
    wiz = caster("w", "wizard", spells=["false-life"], slots={1: 1, 2: 1})
    state = battle(wiz, ("gob", "yard"))
    cast(state, "w", "false-life", ScriptedRng(3))
    assert state.creatures["w"].temp_hp == 7
    assert slots_left(state.creatures["w"], 1) == 0
    state = battle(caster("w", "wizard", spells=["false-life"], slots={2: 1}), ("gob", "yard"))
    cast(state, "w", "false-life", ScriptedRng(1), slot=2)
    assert state.creatures["w"].temp_hp == 10


def test_golden_spell_grease() -> None:
    # Grease: every creature in the 10-ft square (the zone) makes a DEX save DC 13 or falls prone.
    wiz = caster("w", "wizard", spells=["grease"], slots={1: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    events = cast(state, "w", "grease", ScriptedRng(5, 14), zone="yard")
    assert [c.result.dc for c in of(events, CheckResolved)] == [13, 13]
    assert conditions_of(state, "gob") == ["prone"] and conditions_of(state, "gob2") == []
    assert slots_left(state.creatures["w"], 1) == 0


def test_golden_spell_guiding_bolt() -> None:
    # Guiding Bolt: ranged spell attack, 4d6 radiant (+1d6 per slot above 1); the next attack
    # against the target has advantage.
    cleric = caster("c", "cleric", spells=["guiding-bolt"], slots={1: 1, 2: 1})
    state = battle(cleric, ("gob", "yard"), ("b", "gate"))
    events = cast(state, "c", "guiding-bolt", ScriptedRng(10, 1, 2, 3, 4), targets=["gob"])
    assert of(events, AttackRolled)[0].roll.total == 15
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "radiant"
    assert state.creatures["gob"].hp == 20
    assert conditions_of(state, "gob") == ["guided"]
    assert hit_chance(state, "b", "gob", CLAW, REGS.chars.features).adv.value == "advantage"
    state = battle(caster("c", "cleric", spells=["guiding-bolt"], slots={2: 1}), ("gob", "yard"))
    cast(state, "c", "guiding-bolt", ScriptedRng(10, 1, 1, 1, 1, 1), targets=["gob"], slot=2)
    assert state.creatures["gob"].hp == 25


def test_golden_spell_hideous_laughter() -> None:
    # Hideous Laughter: WIS save DC 13 or prone and incapacitated (save ends), concentration.
    wiz = caster("w", "wizard", spells=["hideous-laughter"], slots={1: 1})
    state = battle(wiz, ("gob", "yard"))
    cast(state, "w", "hideous-laughter", ScriptedRng(5), targets=["gob"])
    assert conditions_of(state, "gob") == ["prone", "incapacitated"]
    ends = state.creatures["gob"].conditions[1].save_ends
    assert ends is not None and ends.dc == 13
    conc = state.creatures["w"].concentrating_on
    assert conc is not None and conc.spell_id == "hideous-laughter" and len(conc.links) == 2


def test_golden_spell_inflict_wounds() -> None:
    # Inflict Wounds: melee spell attack, 3d10 necrotic (+1d10 per slot above 1); crit doubles.
    cleric = caster("c", "cleric", spells=["inflict-wounds"], slots={1: 2, 2: 1})
    state = battle(cleric, ("gob", "gate"))
    events = cast(state, "c", "inflict-wounds", ScriptedRng(10, 4, 5, 6), targets=["gob"])
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "necrotic"
    assert state.creatures["gob"].hp == 15
    state = battle(caster("c", "cleric", spells=["inflict-wounds"], slots={1: 1}), ("gob", "gate"))
    cast(state, "c", "inflict-wounds", ScriptedRng(20, 1, 2, 3, 4, 5, 6), targets=["gob"])
    assert state.creatures["gob"].hp == 9


def test_golden_spell_mage_armor() -> None:
    # Mage Armor: AC 13 + DEX for an unarmored target, modelled as +3 AC for 8 hours (4800 rounds).
    wiz = caster("w", "wizard", spells=["mage-armor"], slots={1: 1})
    state = battle(wiz, ("b", "gate"), ("gob", "gate"))
    base = state.creatures["b"].ac
    cast(state, "w", "mage-armor", ScriptedRng(), targets=["b"])
    assert condition_ac_bonus(state.creatures["b"]) == 3
    assert state.creatures["b"].conditions[0].rounds_left == 4800
    assert hit_chance(state, "gob", "b", CLAW, REGS.chars.features).target_ac == base + 3
    assert slots_left(state.creatures["w"], 1) == 0


def test_golden_spell_thunderwave() -> None:
    # Thunderwave: everyone else in the caster's zone, CON save DC 13, 2d8 thunder (+1d8 per slot
    # above 1) rolled once, half on a success.
    wiz = caster("w", "wizard", spells=["thunderwave"], slots={1: 1, 2: 1})
    state = battle(wiz, ("gob", "gate"), ("gob2", "gate"))
    events = cast(state, "w", "thunderwave", ScriptedRng(5, 3, 4, 14))
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "thunder"
    assert (state.creatures["gob"].hp, state.creatures["gob2"].hp) == (23, 27)
    state = battle(caster("w", "wizard", spells=["thunderwave"], slots={2: 1}), ("gob", "gate"))
    cast(state, "w", "thunderwave", ScriptedRng(5, 1, 1, 1), slot=2)
    assert state.creatures["gob"].hp == 27
