"""Golden numbers for the shipped level 3 spells (SRD 5.1 spell descriptions).

Casters are level 5 with casting ability 16 (+3) and proficiency +3: spell save DC 14 (read
from the sheet). Rolls are scripted. Monsters have AC 13, 30 HP and all ability scores 10, so
a save succeeds on a natural 14 or more.
"""

from __future__ import annotations

import pytest

from aidm.models.commands import RefusalCode
from aidm.models.events import CheckResolved, DamageTaken
from aidm.rules.command_checks import CommandRefused
from aidm.rules.condition_timing import new_condition
from aidm.rules.conditions import can_take_reactions, condition_ac_bonus, speed_multiplier
from aidm.rules.zones import zone_path
from tests.unit.rules.combat_fixtures import ScriptedRng, economy
from tests.unit.rules.spell_fixtures import (
    battle,
    cast,
    caster,
    conditions_of,
    next_turn,
    of,
    slots_left,
)


def test_golden_spell_fear() -> None:
    # Fear: everyone else in the cone (the caster's zone), WIS save or frightened (save ends).
    wiz = caster("w", "wizard", spells=["fear"], level=5, slots={3: 1})
    state = battle(wiz, ("gob", "gate"), ("gob2", "gate"))
    events = cast(state, "w", "fear", ScriptedRng(5, 20))
    dc = of(events, CheckResolved)[0].result.dc
    assert dc == 14
    assert conditions_of(state, "gob") == ["frightened"] and conditions_of(state, "gob2") == []
    ends = state.creatures["gob"].conditions[0].save_ends
    assert ends is not None and ends.dc == dc
    conc = state.creatures["w"].concentrating_on
    assert conc is not None and conc.spell_id == "fear"
    assert slots_left(state.creatures["w"], 3) == 0


def test_golden_spell_fireball() -> None:
    # Fireball: DEX save, 8d6 fire rolled once, half on a success; range 150 ft (two hops).
    wiz = caster("w", "wizard", spells=["fireball"], level=5, slots={3: 1})
    state = battle(wiz, ("gob", "wall"), ("gob2", "wall"))
    dice = (1, 2, 3, 4, 5, 6, 1, 2)
    events = cast(state, "w", "fireball", ScriptedRng(5, *dice, 20), zone="wall")
    assert [c.result.dc for c in of(events, CheckResolved)] == [14, 14]
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "fire"
    assert [d.total for d in of(events, DamageTaken)] == [24, 12]
    assert (state.creatures["gob"].hp, state.creatures["gob2"].hp) == (6, 18)
    assert slots_left(state.creatures["w"], 3) == 0


def test_golden_spell_lightning_bolt() -> None:
    # Lightning Bolt: a 100-ft line aimed at one zone (own or next, M29.7d), DEX save, 8d6
    # lightning, half on a save. Aimed at the yard (30 ft away): the gate is spared.
    wiz = caster("w", "wizard", spells=["lightning-bolt"], level=5, slots={3: 1})
    state = battle(wiz, ("gob", "gate"), ("gob2", "yard"))
    dice = (6, 6, 6, 6, 1, 1, 1, 1)
    events = cast(state, "w", "lightning-bolt", ScriptedRng(5, *dice, 20), zone="yard")
    assert of(events, DamageTaken)[0].parts[0].damage_type.value == "lightning"
    assert [d.total for d in of(events, DamageTaken)] == [28]
    assert (state.creatures["gob"].hp, state.creatures["gob2"].hp) == (30, 2)


def test_golden_spell_mass_healing_word() -> None:
    # Mass Healing Word: bonus action, up to six creatures, 1d4 + WIS 3 + Disciple of Life 5.
    cleric = caster("c", "cleric", spells=["mass-healing-word"], level=5, slots={3: 1})
    state = battle(cleric, ("b", "gate"), ("b2", "yard"))
    for cid in ("b", "b2"):
        state.creatures[cid].max_hp = 30
        state.creatures[cid].hp = 1
    cast(state, "c", "mass-healing-word", ScriptedRng(2, 3), targets=["b", "b2"])
    assert (state.creatures["b"].hp, state.creatures["b2"].hp) == (11, 12)
    assert economy(state, "c").action and not economy(state, "c").bonus_action


def test_golden_spell_slow() -> None:
    # Slow: WIS save, speed halved, -2 AC, no reactions; concentration, one minute.
    wiz = caster("w", "wizard", spells=["slow"], level=5, slots={3: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    cast(state, "w", "slow", ScriptedRng(5, 20), targets=["gob", "gob2"])
    gob = state.creatures["gob"]
    assert conditions_of(state, "gob") == ["slowed"] and conditions_of(state, "gob2") == []
    assert speed_multiplier(gob) == 0.5 and condition_ac_bonus(gob) == -2
    assert not can_take_reactions(gob)
    assert gob.conditions[0].rounds_left == 10


def test_golden_spell_hypnotic_pattern() -> None:
    # Hypnotic Pattern: WIS save or charmed and incapacitated (save ends), concentration.
    wiz = caster("w", "wizard", spells=["hypnotic-pattern"], level=5, slots={3: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    cast(state, "w", "hypnotic-pattern", ScriptedRng(5, 20), zone="yard")
    assert conditions_of(state, "gob") == ["charmed", "incapacitated"]
    assert conditions_of(state, "gob2") == []
    conc = state.creatures["w"].concentrating_on
    assert conc is not None and conc.spell_id == "hypnotic-pattern" and len(conc.links) == 2


def test_golden_spell_spirit_guardians() -> None:
    # Spirit Guardians: an aura around the caster; an enemy starting its turn there makes a WIS
    # save DC 14 or takes 3d8 radiant (half on a success); allies are spared; it follows the
    # caster (BG3) and ends with the concentration.
    cleric = caster("c", "cleric", spells=["spirit-guardians"], level=5, slots={3: 1})
    state = battle(cleric, ("gob", "gate"), ("b", "gate"))
    cast(state, "c", "spirit-guardians", ScriptedRng())
    events = next_turn(state, ScriptedRng(5, 2, 3, 4))  # gob: WIS 5 fails, 3d8 = 9
    assert of(events, CheckResolved)[0].result.dc == 14
    assert state.creatures["gob"].hp == 21
    hp = state.creatures["b"].hp
    assert (
        of(next_turn(state, ScriptedRng()), CheckResolved) == [] and state.creatures["b"].hp == hp
    )


def test_golden_spell_stinking_cloud() -> None:
    # Stinking Cloud: heavily obscured (blinded inside); a creature starting its turn inside
    # makes a CON save DC 14 or loses its turn retching (BG3 nauseated: no actions or reactions).
    wiz = caster("w", "wizard", spells=["stinking-cloud"], level=5, slots={3: 1})
    state = battle(wiz, ("gob", "yard"))
    cast(state, "w", "stinking-cloud", ScriptedRng(), zone="yard")
    assert conditions_of(state, "gob") == ["blinded"]
    events = next_turn(state, ScriptedRng(6))
    assert of(events, CheckResolved)[0].result.dc == 14
    assert sorted(conditions_of(state, "gob")) == ["blinded", "nauseated"]
    assert not economy(state, "gob").action and not economy(state, "gob").reaction


def test_golden_spell_sleet_storm() -> None:
    # Sleet Storm: difficult terrain, heavily obscured; a creature entering or starting its turn
    # there makes a DEX save DC 14 or falls prone.
    wiz = caster("w", "wizard", spells=["sleet-storm"], level=5, slots={3: 1})
    state = battle(wiz, ("gob", "yard"))
    cast(state, "w", "sleet-storm", ScriptedRng(), zone="yard")
    next_turn(state, ScriptedRng(3))
    assert sorted(conditions_of(state, "gob")) == ["blinded", "prone"]
    assert state.encounter is not None
    assert zone_path(state.encounter.zone_map, "gate", "yard").feet == 60


def test_golden_spell_revivify() -> None:
    # Revivify: touch a dead creature: it returns to life with 1 hit point (BG3: no time limit).
    cleric = caster("c", "cleric", spells=["revivify"], level=5, slots={3: 2})
    state = battle(cleric, ("b", "gate"))
    with pytest.raises(CommandRefused) as refused:
        cast(state, "c", "revivify", ScriptedRng(), targets=["b"])
    assert refused.value.code is RefusalCode.INVALID_TARGET
    b = state.creatures["b"]
    b.hp, b.dead, b.death_save_failures = 0, True, 3
    b.conditions.append(new_condition("unconscious", source_id="zero_hp"))
    cast(state, "c", "revivify", ScriptedRng(), targets=["b"])
    b = state.creatures["b"]
    assert (b.dead, b.hp, b.death_save_failures, b.conditions) == (False, 1, 0, [])
