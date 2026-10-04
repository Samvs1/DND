"""Golden numbers for the shipped cantrips (SRD 5.1 spell descriptions).

Casters have their casting ability at 16 (+3) and proficiency +2: spell save DC 13, spell
attack +5. Rolls are scripted, so every number is exact. Monsters here have AC 13, 30 HP and
all ability scores 10 (a save succeeds on a natural 13 or more).
"""

from __future__ import annotations

from aidm.models.combat import AttackProfile
from aidm.models.combat_events import AttackRolled
from aidm.models.events import CheckResolved, DamageTaken
from aidm.rules.conditions import can_take_reactions, speed_multiplier
from aidm.rules.hit_chance import hit_chance
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng
from tests.unit.rules.spell_fixtures import battle, cast, caster, conditions_of, of


def test_golden_spell_acid_splash() -> None:
    # Acid Splash: up to two creatures, DEX save DC 13, 1d6 acid (2d6 at character level 5).
    wiz = caster("w", "wizard", cantrips=["acid-splash"])
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    events = cast(state, "w", "acid-splash", ScriptedRng(5, 4, 14), targets=["gob", "gob2"])
    assert [c.result.dc for c in of(events, CheckResolved)] == [13, 13]
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "acid"
    assert (state.creatures["gob"].hp, state.creatures["gob2"].hp) == (26, 30)
    wiz = caster("w", "wizard", cantrips=["acid-splash"], level=5)
    state = battle(wiz, ("gob", "yard"))
    cast(state, "w", "acid-splash", ScriptedRng(5, 3, 4), targets=["gob"])
    assert state.creatures["gob"].hp == 23


def test_golden_spell_chill_touch() -> None:
    # Chill Touch: ranged spell attack (+5 vs AC 13), 1d8 necrotic; 2d8 at level 5.
    wiz = caster("w", "wizard", cantrips=["chill-touch"])
    state = battle(wiz, ("gob", "yard"))
    events = cast(state, "w", "chill-touch", ScriptedRng(10, 6), targets=["gob"])
    assert of(events, AttackRolled)[0].roll.total == 15
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "necrotic"
    assert state.creatures["gob"].hp == 24
    state = battle(caster("w", "wizard", cantrips=["chill-touch"]), ("gob", "yard"))
    events = cast(state, "w", "chill-touch", ScriptedRng(7), targets=["gob"])
    assert not of(events, AttackRolled)[0].hit and state.creatures["gob"].hp == 30
    state = battle(caster("w", "wizard", cantrips=["chill-touch"], level=5), ("gob", "yard"))
    cast(state, "w", "chill-touch", ScriptedRng(10, 3, 4), targets=["gob"])
    assert state.creatures["gob"].hp == 23


def test_golden_spell_poison_spray() -> None:
    # Poison Spray: range 10 ft (same zone), CON save DC 13, 1d12 poison, nothing on a success.
    wiz = caster("w", "wizard", cantrips=["poison-spray"])
    state = battle(wiz, ("gob", "gate"))
    events = cast(state, "w", "poison-spray", ScriptedRng(12, 9), targets=["gob"])
    assert of(events, CheckResolved)[0].result.dc == 13
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "poison"
    assert state.creatures["gob"].hp == 21
    state = battle(caster("w", "wizard", cantrips=["poison-spray"]), ("gob", "gate"))
    assert not of(cast(state, "w", "poison-spray", ScriptedRng(13), targets=["gob"]), DamageTaken)
    state = battle(caster("w", "wizard", cantrips=["poison-spray"], level=11), ("gob", "gate"))
    cast(state, "w", "poison-spray", ScriptedRng(1, 5, 6, 7), targets=["gob"])
    assert state.creatures["gob"].hp == 12


def test_golden_spell_ray_of_frost() -> None:
    # Ray of Frost: ranged spell attack, 1d8 cold, and the target's speed is reduced (chilled).
    wiz = caster("w", "wizard", cantrips=["ray-of-frost"])
    state = battle(wiz, ("gob", "yard"))
    events = cast(state, "w", "ray-of-frost", ScriptedRng(10, 5), targets=["gob"])
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "cold"
    assert state.creatures["gob"].hp == 25
    assert conditions_of(state, "gob") == ["chilled"]
    assert speed_multiplier(state.creatures["gob"]) == 0.67
    state = battle(caster("w", "wizard", cantrips=["ray-of-frost"]), ("gob", "yard"))
    cast(state, "w", "ray-of-frost", ScriptedRng(2), targets=["gob"])
    assert conditions_of(state, "gob") == []


def test_golden_spell_shocking_grasp() -> None:
    # Shocking Grasp: melee spell attack, 1d8 lightning, the target cannot take reactions.
    wiz = caster("w", "wizard", cantrips=["shocking-grasp"])
    state = battle(wiz, ("gob", "gate"))
    events = cast(state, "w", "shocking-grasp", ScriptedRng(12, 4), targets=["gob"])
    assert of(events, AttackRolled)[0].roll.total == 17
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "lightning"
    assert state.creatures["gob"].hp == 26
    assert not can_take_reactions(state.creatures["gob"])


def test_golden_spell_true_strike() -> None:
    # True Strike: the caster has advantage on the first attack roll of the next turn.
    wiz = caster("w", "wizard", cantrips=["true-strike"])
    state = battle(wiz, ("gob", "gate"))
    cast(state, "w", "true-strike", ScriptedRng())
    assert conditions_of(state, "w") == ["true-strike"]
    claw = AttackProfile(key="stab", name="Stab", attack_bonus=4)
    chance = hit_chance(state, "w", "gob", claw, REGS.chars.features)
    assert chance.adv.value == "advantage"
