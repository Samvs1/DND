"""Golden numbers for the 10 reference spells of the DSL (SRD 5.1 spell descriptions).

Casters have their casting ability at 16 (+3) and proficiency +2: spell save DC 13, spell
attack +5 (SRD 5.1 Spellcasting). Rolls are scripted, so every number is exact.
"""

from __future__ import annotations

import random

from aidm.models.combat import AttackProfile
from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.commands import AttackCommand, EndTurnCommand
from aidm.models.events import CheckResolved, DamageTaken, DiceRolled
from aidm.rules.conditions import condition_ac_bonus
from aidm.rules.hit_chance import hit_chance
from aidm.rules.turns import begin_turn
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, do, economy
from tests.unit.rules.spell_fixtures import battle, cast, caster, of, slots_left


def test_golden_spell_fire_bolt() -> None:
    # Fire Bolt: ranged spell attack, 120 ft (yard is 1 hop), 1d10 fire; 2d10 at level 5.
    state = battle(caster("w", "wizard", cantrips=["fire-bolt"]), ("gob", "yard"))
    events = cast(state, "w", "fire-bolt", ScriptedRng(8, 7), targets=["gob"])
    assert of(events, AttackRolled)[0].roll.total == 13
    assert of(events, DamageTaken)[0].total == 7
    state = battle(caster("w", "wizard", cantrips=["fire-bolt"], level=5), ("gob", "yard"))
    events = cast(state, "w", "fire-bolt", ScriptedRng(8, 4, 6), targets=["gob"])
    assert of(events, DiceRolled)[0].roll.expression == "2d10"
    assert state.creatures["gob"].hp == 20


def test_golden_spell_sacred_flame() -> None:
    # Sacred Flame: DEX save vs DC 13, 1d8 radiant on a failure, nothing on a success.
    state = battle(caster("c", "cleric", cantrips=["sacred-flame"]), ("gob", "yard"))
    events = cast(state, "c", "sacred-flame", ScriptedRng(12, 5), targets=["gob"])
    assert of(events, CheckResolved)[0].result.dc == 13
    assert of(events, DamageTaken)[0].total == 5
    state = battle(caster("c", "cleric", cantrips=["sacred-flame"]), ("gob", "yard"))
    assert not of(cast(state, "c", "sacred-flame", ScriptedRng(13), targets=["gob"]), DamageTaken)


def test_golden_spell_eldritch_blast_two_beams_at_level_5() -> None:
    # Eldritch Blast: two beams at character level 5, each a ranged spell attack for 1d10 force.
    state = battle(caster("k", "warlock", cantrips=["eldritch-blast"], level=5), ("gob", "yard"))
    events = cast(state, "k", "eldritch-blast", ScriptedRng(10, 4, 1), targets=["gob"])
    rolls = of(events, AttackRolled)
    assert [r.hit for r in rolls] == [True, False]
    assert state.creatures["gob"].hp == 26


def test_golden_spell_magic_missile() -> None:
    # Magic Missile: three darts of 1d4+1 force that always hit; +1 dart per slot level above 1.
    wiz = caster("w", "wizard", spells=["magic-missile"], slots={1: 2, 2: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    cast(state, "w", "magic-missile", ScriptedRng(1, 2, 3), targets=["gob"])
    assert state.creatures["gob"].hp == 21
    assert slots_left(state.creatures["w"], 1) == 1
    state = battle(
        caster("w", "wizard", spells=["magic-missile"], slots={2: 1}),
        ("gob", "yard"),
        ("gob2", "yard"),
    )
    cast(state, "w", "magic-missile", ScriptedRng(1, 1, 1, 1), targets=["gob", "gob2"], slot=2)
    assert (state.creatures["gob"].hp, state.creatures["gob2"].hp) == (26, 26)


def test_golden_spell_cure_wounds() -> None:
    # Cure Wounds: 1d8 + WIS 3, + Disciple of Life (2 + spell level); 2d8 when cast at level 2.
    cleric = caster("c", "cleric", spells=["cure-wounds"], slots={1: 2, 2: 1})
    state = battle(cleric, ("b", "gate"))
    state.creatures["b"].hp = 1
    cast(state, "c", "cure-wounds", ScriptedRng(4), targets=["b"])
    assert state.creatures["b"].hp == 11
    state = battle(caster("c", "cleric", spells=["cure-wounds"], slots={2: 1}), ("b", "gate"))
    state.creatures["b"].hp = 1
    events = cast(state, "c", "cure-wounds", ScriptedRng(1, 1), targets=["b"], slot=2)
    assert of(events, SpellCast)[0].cast_level == 2
    assert state.creatures["b"].hp == 1 + 2 + 3 + 4


def test_golden_spell_healing_word_is_a_bonus_action() -> None:
    # Healing Word: bonus action, 60 ft (1 hop), 1d4 + WIS 3 + Disciple of Life 3.
    state = battle(caster("c", "cleric", spells=["healing-word"]), ("b", "yard"))
    state.creatures["b"].hp = 1
    cast(state, "c", "healing-word", ScriptedRng(3), targets=["b"])
    assert state.creatures["b"].hp == 10
    assert economy(state, "c").action and not economy(state, "c").bonus_action


def test_golden_spell_bless() -> None:
    # Bless: up to 3 creatures, concentration, +1d4 to attack rolls (and saves).
    state = battle(caster("c", "cleric", spells=["bless"]), ("b", "gate"), ("gob", "gate"))
    cast(state, "c", "bless", ScriptedRng(), targets=["c", "b"])
    assert [c.name for c in state.creatures["b"].conditions] == ["blessed"]
    conc = state.creatures["c"].concentrating_on
    assert conc is not None and conc.spell_id == "bless" and len(conc.links) == 2
    do(state, EndTurnCommand(actor_id="c"), ScriptedRng())
    for event in begin_turn(random.Random(0), state):
        apply(state, event)
    events = do(state, AttackCommand(actor_id="b", target_id="gob"), ScriptedRng(6, 2, 5))
    rolled = of(events, AttackRolled)[0]
    assert rolled.roll.total + rolled.bonus_rolls[0].total == 13 and rolled.hit
    assert [r.expression for r in rolled.bonus_rolls] == ["1d4"]


def test_golden_spell_burning_hands() -> None:
    # Burning Hands: everyone else in the caster's zone, DEX save DC 13, 3d6 fire rolled once,
    # half on a success. Targets in initiative order: gob (fail), gob2 (success), b (success).
    wiz = caster("w", "wizard", spells=["burning-hands"])
    state = battle(wiz, ("gob", "gate"), ("gob2", "gate"), ("b", "gate"))
    events = cast(state, "w", "burning-hands", ScriptedRng(5, 3, 4, 5, 15, 12))
    assert [d.total for d in of(events, DamageTaken)] == [12, 6, 6]
    assert len(of(events, DiceRolled)) == 1
    assert state.creatures["b"].hp == 6


def test_golden_spell_hold_person() -> None:
    # Hold Person: WIS save DC 13 or paralyzed (save ends, concentration); +1 target per level.
    cleric = caster("c", "cleric", spells=["hold-person"], level=3, slots={2: 2, 3: 1})
    state = battle(cleric, ("gob", "yard"), ("gob2", "yard"))
    cast(state, "c", "hold-person", ScriptedRng(5), targets=["gob"])
    held = state.creatures["gob"].conditions[0]
    assert held.name == "paralyzed" and held.save_ends is not None and held.save_ends.dc == 13
    state = battle(
        caster("c", "cleric", spells=["hold-person"], level=5, slots={3: 1}),
        ("gob", "yard"),
        ("gob2", "yard"),
    )
    cast(state, "c", "hold-person", ScriptedRng(5, 20), targets=["gob", "gob2"], slot=3)
    assert [len(state.creatures[g].conditions) for g in ("gob", "gob2")] == [1, 0]


def test_golden_spell_shield_of_faith() -> None:
    # Shield of Faith: bonus action, +2 AC, concentration; a new concentration spell ends it.
    cleric = caster("c", "cleric", spells=["shield-of-faith", "bless"], slots={1: 2})
    state = battle(cleric, ("b", "gate"), ("gob", "gate"))
    cast(state, "c", "shield-of-faith", ScriptedRng(), targets=["b"])
    assert condition_ac_bonus(state.creatures["b"]) == 2
    claw = AttackProfile(key="claw", name="Claw", attack_bonus=4)
    assert hit_chance(state, "gob", "b", claw, REGS.chars.features).target_ac == 20
    cast(state, "c", "bless", ScriptedRng(), targets=["c"])
    assert condition_ac_bonus(state.creatures["b"]) == 0
