"""Golden numbers for the shipped level 2 spells (SRD 5.1 spell descriptions).

Casters have their casting ability at 16 (+3) and proficiency +2: spell save DC 13, spell
attack +5. Rolls are scripted. Monsters have AC 13, 30 HP and all ability scores 10.
"""

from __future__ import annotations

from aidm.models.combat import AttackProfile
from aidm.models.combat_events import AttackRolled
from aidm.models.events import CheckResolved, DamageTaken
from aidm.rules.condition_timing import new_condition
from aidm.rules.hit_chance import hit_chance
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng
from tests.unit.rules.spell_fixtures import battle, cast, caster, conditions_of, of, slots_left

CLAW = AttackProfile(key="claw", name="Claw", attack_bonus=4)


def test_golden_spell_acid_arrow() -> None:
    # Melf's Acid Arrow: ranged spell attack, 4d4 acid on a hit (+1d4 per slot above 2).
    wiz = caster("w", "wizard", spells=["acid-arrow"], slots={2: 1, 3: 1})
    state = battle(wiz, ("gob", "yard"))
    events = cast(state, "w", "acid-arrow", ScriptedRng(10, 1, 2, 3, 4), targets=["gob"])
    assert of(events, AttackRolled)[0].roll.total == 15
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "acid"
    assert state.creatures["gob"].hp == 20 and slots_left(state.creatures["w"], 2) == 0
    state = battle(caster("w", "wizard", spells=["acid-arrow"], slots={3: 1}), ("gob", "yard"))
    cast(state, "w", "acid-arrow", ScriptedRng(10, 1, 1, 1, 1, 1), targets=["gob"], slot=3)
    assert state.creatures["gob"].hp == 25


def test_golden_spell_aid() -> None:
    # Aid: up to three creatures gain 5 hit points (modelled as temp HP); +5 per slot above 2.
    cleric = caster("c", "cleric", spells=["aid"], slots={2: 1, 3: 1})
    state = battle(cleric, ("b", "gate"), ("b2", "yard"))
    cast(state, "c", "aid", ScriptedRng(), targets=["c", "b", "b2"])
    assert [state.creatures[c].temp_hp for c in ("c", "b", "b2")] == [5, 5, 5]
    assert slots_left(state.creatures["c"], 2) == 0
    state = battle(caster("c", "cleric", spells=["aid"], slots={3: 1}), ("b", "gate"))
    cast(state, "c", "aid", ScriptedRng(), targets=["b"], slot=3)
    assert state.creatures["b"].temp_hp == 10


def test_golden_spell_blindness_deafness() -> None:
    # Blindness/Deafness: CON save DC 13 or blinded for 1 minute (10 rounds), save ends each
    # turn; +1 target per slot above 2.
    wiz = caster("w", "wizard", spells=["blindness-deafness"], slots={2: 1})
    state = battle(wiz, ("gob", "yard"))
    events = cast(state, "w", "blindness-deafness", ScriptedRng(5), targets=["gob"])
    assert of(events, CheckResolved)[0].result.dc == 13
    blinded = state.creatures["gob"].conditions[0]
    assert blinded.name == "blinded" and blinded.rounds_left == 10
    assert blinded.save_ends is not None and blinded.save_ends.dc == 13
    state = battle(
        caster("w", "wizard", spells=["blindness-deafness"], level=5, slots={3: 1}),
        ("gob", "yard"),
        ("gob2", "yard"),
    )
    cast(state, "w", "blindness-deafness", ScriptedRng(5, 20), targets=["gob", "gob2"], slot=3)
    assert [len(state.creatures[g].conditions) for g in ("gob", "gob2")] == [1, 0]


def test_golden_spell_blur() -> None:
    # Blur: concentration, attack rolls against the caster have disadvantage.
    wiz = caster("w", "wizard", spells=["blur"], slots={2: 1})
    state = battle(wiz, ("gob", "gate"))
    cast(state, "w", "blur", ScriptedRng())
    assert conditions_of(state, "w") == ["blurred"]
    conc = state.creatures["w"].concentrating_on
    assert conc is not None and conc.spell_id == "blur"
    chance = hit_chance(state, "gob", "w", CLAW, REGS.chars.features)
    assert chance.adv.value == "disadvantage"


def test_golden_spell_invisibility() -> None:
    # Invisibility: touch, concentration; advantage on the bearer's attacks, disadvantage against.
    wiz = caster("w", "wizard", spells=["invisibility"], slots={2: 1})
    state = battle(wiz, ("b", "gate"), ("gob", "gate"))
    cast(state, "w", "invisibility", ScriptedRng(), targets=["b"])
    assert conditions_of(state, "b") == ["invisibility"]
    assert state.creatures["b"].conditions[0].rounds_left == 600
    mine = hit_chance(state, "b", "gob", CLAW, REGS.chars.features)
    theirs = hit_chance(state, "gob", "b", CLAW, REGS.chars.features)
    assert (mine.adv.value, theirs.adv.value) == ("advantage", "disadvantage")


def test_golden_spell_lesser_restoration() -> None:
    # Lesser Restoration: ends blinded, deafened, paralyzed or poisoned (here two are present).
    cleric = caster("c", "cleric", spells=["lesser-restoration"], slots={2: 1})
    state = battle(cleric, ("b", "gate"))
    for name in ("blinded", "poisoned", "prone"):
        state.creatures["b"].conditions.append(new_condition(name))
    cast(state, "c", "lesser-restoration", ScriptedRng(), targets=["b"])
    assert conditions_of(state, "b") == ["prone"]
    assert slots_left(state.creatures["c"], 2) == 0


def test_golden_spell_scorching_ray() -> None:
    # Scorching Ray: three ranged spell attacks of 2d6 fire (+1 ray per slot above 2); a crit
    # doubles the dice. Rays: hit for 7, miss, critical hit for 4d6 = 10.
    wiz = caster("w", "wizard", spells=["scorching-ray"], slots={2: 1, 3: 1})
    state = battle(wiz, ("gob", "yard"))
    script = ScriptedRng(10, 3, 4, 5, 20, 1, 2, 3, 4)
    events = cast(state, "w", "scorching-ray", script, targets=["gob"])
    assert [r.hit for r in of(events, AttackRolled)] == [True, False, True]
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "fire"
    assert state.creatures["gob"].hp == 30 - 7 - 10
    state = battle(caster("w", "wizard", spells=["scorching-ray"], slots={3: 1}), ("gob", "yard"))
    rolls = [10, 1, 1] * 4
    cast(state, "w", "scorching-ray", ScriptedRng(*rolls), targets=["gob"], slot=3)
    assert state.creatures["gob"].hp == 22


def test_golden_spell_shatter() -> None:
    # Shatter: CON save DC 13, 3d8 thunder rolled once (+1d8 per slot above 2), half on a save.
    wiz = caster("w", "wizard", spells=["shatter"], slots={2: 1, 3: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    events = cast(state, "w", "shatter", ScriptedRng(5, 3, 4, 5, 14), zone="yard")
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "thunder"
    assert (state.creatures["gob"].hp, state.creatures["gob2"].hp) == (18, 24)
    state = battle(caster("w", "wizard", spells=["shatter"], slots={3: 1}), ("gob", "yard"))
    cast(state, "w", "shatter", ScriptedRng(5, 1, 1, 1, 1), zone="yard", slot=3)
    assert state.creatures["gob"].hp == 26


def test_golden_spell_web() -> None:
    # Web: DEX save DC 13 or restrained, concentration, one hour. M3.7: the web is a zone
    # surface (difficult terrain, the save repeats on entering and at turn start, the restraint
    # lasts while inside and ends with the surface, i.e. with the concentration).
    wiz = caster("w", "wizard", spells=["web"], slots={2: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    cast(state, "w", "web", ScriptedRng(5, 14), zone="yard")
    assert conditions_of(state, "gob") == ["restrained"] and conditions_of(state, "gob2") == []
    assert state.creatures["gob"].conditions[0].source_id == "surface:yard:web"
    conc = state.creatures["w"].concentrating_on
    assert conc is not None and conc.spell_id == "web"
    assert state.encounter is not None
    web = state.encounter.zone_map.zone("yard").surfaces[0]
    assert (web.kind, web.dc, web.concentration, web.rounds_left) == ("web", 13, True, 600)
