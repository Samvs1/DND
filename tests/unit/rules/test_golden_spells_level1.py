"""Golden numbers for the shipped level 1 spells beyond the 10 reference spells (SRD 5.1).

Casters have their casting ability at 16 (+3) and proficiency +2: spell save DC 13, spell
attack +5. Rolls are scripted. Monsters have AC 13, 30 HP and all ability scores 10.
"""

from __future__ import annotations

from aidm.models.abilities import Ability
from aidm.models.combat import AttackProfile
from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.commands import DashCommand
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.encounter import Side
from aidm.models.encounter_events import EconomyChanged
from aidm.models.events import CheckResolved, ConditionRemoved, DamageTaken
from aidm.models.state import GameState
from aidm.rules.attacks import resolve_attack
from aidm.rules.conditions import condition_ac_bonus, save_with_conditions
from aidm.rules.damage import resolve_damage
from aidm.rules.hit_chance import hit_chance
from aidm.rules.turns import fresh_economy
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, do, economy, fight
from tests.unit.rules.monster_fixtures import srd_monster
from tests.unit.rules.spell_fixtures import battle, cast, caster, conditions_of, of, slots_left

CLAW = AttackProfile(key="claw", name="Claw", attack_bonus=4)


def test_golden_spell_animal_friendship() -> None:
    # Animal Friendship (ranger, level 2): a beast only; WIS save DC 13 or befriended (charmed,
    # ends on the party's harm) for 24 hours (14400 rounds). The wolf has WIS 12 (+1).
    def wolf_fight() -> GameState:
        ranger = caster("r", "ranger", spells=["animal-friendship"], level=2, slots={1: 2})
        return fight(
            [(ranger, Side.PARTY, "gate"), (srd_monster("wolf", "wolf-1"), Side.HOSTILE, "yard")]
        )

    state = wolf_fight()
    events = cast(state, "r", "animal-friendship", ScriptedRng(5), targets=["wolf-1"])
    assert of(events, CheckResolved)[0].result.dc == 13
    charmed = state.creatures["wolf-1"].conditions[0]
    assert charmed.name == "befriended" and charmed.rounds_left == 14400
    assert slots_left(state.creatures["r"], 1) == 1
    state = wolf_fight()
    cast(state, "r", "animal-friendship", ScriptedRng(12), targets=["wolf-1"])
    assert conditions_of(state, "wolf-1") == []


def test_golden_spell_charm_person() -> None:
    # Charm Person: WIS save DC 13, charmed for 1 hour (600 rounds); +1 target per slot above 1.
    wiz = caster("w", "wizard", spells=["charm-person"], slots={2: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    events = cast(state, "w", "charm-person", ScriptedRng(5, 5), targets=["gob", "gob2"], slot=2)
    assert of(events, SpellCast)[0].cast_level == 2
    assert [conditions_of(state, g) for g in ("gob", "gob2")] == [["befriended"], ["befriended"]]
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


def test_golden_spell_bane() -> None:
    # Bane: up to three creatures within 30 ft, CHA save DC 13 or -1d4 on attacks and saves.
    cleric = caster("c", "cleric", spells=["bane"], slots={1: 1})
    state = battle(cleric, ("gob", "yard"), ("gob2", "yard"))
    events = cast(state, "c", "bane", ScriptedRng(5, 15), targets=["gob", "gob2"])
    assert [c.result.dc for c in of(events, CheckResolved)] == [13, 13]
    assert conditions_of(state, "gob") == ["bane"] and conditions_of(state, "gob2") == []
    save = save_with_conditions(ScriptedRng(4, 12), state.creatures["gob"], Ability.DEX, 10)
    assert save.roll.total == 8 and not save.success  # d20 12 + DEX 0 - d4 4
    dart = AttackProfile(key="dart", name="Dart", attack_bonus=4, ranged=True, range_normal=60)
    state.creatures["c"].ac = 18
    chance = hit_chance(state, "gob", "c", dart, REGS.chars.features)
    clean = hit_chance(state, "gob2", "c", dart, REGS.chars.features)
    assert chance.bonus_dice == ("-1d4",) and clean.bonus_dice == ()
    # +4 vs AC 18: natural 14+ (0.35) without Bane; with it 0.175 + natural 20 0.05 = 0.225.
    assert (round(clean.probability, 4), round(chance.probability, 4)) == (0.35, 0.225)


def test_golden_spell_longstrider() -> None:
    # Longstrider: touch, one hour, speed +10 ft (+1 creature per slot level above 1).
    wiz = caster("w", "wizard", spells=["longstrider"], slots={1: 1, 2: 1})
    state = battle(wiz, ("b", "gate"))
    cast(state, "w", "longstrider", ScriptedRng(), targets=["w", "b"], slot=2)
    for cid in ("w", "b"):
        creature = state.creatures[cid]
        assert fresh_economy(creature).movement_left == creature.speed + 10
    assert state.creatures["w"].conditions[0].rounds_left == 600


def test_golden_spell_hunters_mark() -> None:
    # Hunter's Mark: bonus action, concentration; the caster's weapon hits on the target deal
    # an extra 1d6 (of the weapon's damage type).
    ranger = caster("r", "ranger", spells=["hunters-mark"], level=2, slots={1: 2})
    state = battle(ranger, ("gob", "yard"))
    cast(state, "r", "hunters-mark", ScriptedRng(), targets=["gob"])
    assert economy(state, "r").action and not economy(state, "r").bonus_action
    bow = AttackProfile(
        key="bow",
        name="Bow",
        attack_bonus=5,
        damage="1d8+3",
        damage_type=DamageType.PIERCING,
        ranged=True,
        range_normal=150,
    )
    result = resolve_attack(ScriptedRng(15, 4, 5), state, "r", "gob", bow, REGS.chars.features)
    taken = of(result.events, DamageTaken)[0]
    assert [(p.damage_type.value, p.rolled) for p in taken.parts] == [
        ("piercing", 7),
        ("piercing", 5),
    ]


def test_golden_spell_sleep() -> None:
    # Sleep: 5d8 hit points of creatures in the area fall asleep, lowest current HP first; a
    # sleeper wakes when it takes damage.
    wiz = caster("w", "wizard", spells=["sleep"], slots={1: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    state.creatures["gob"].hp, state.creatures["gob2"].hp = 12, 5
    cast(state, "w", "sleep", ScriptedRng(3, 3, 3, 3, 3), zone="yard")  # pool 15: 5 used, 10 < 12
    assert conditions_of(state, "gob2") == ["asleep"] and conditions_of(state, "gob") == []
    hit = resolve_damage(
        state.creatures["gob2"], [DamagePacket(amount=1, damage_type=DamageType.FIRE)]
    )
    assert [e.name for e in of(hit, ConditionRemoved)] == ["asleep"]


def test_golden_spell_color_spray() -> None:
    # Color Spray: 6d10 hit points of creatures in the cone (the caster's zone), lowest HP first,
    # are blinded until the end of the caster's next turn.
    wiz = caster("w", "wizard", spells=["color-spray"], slots={1: 1})
    state = battle(wiz, ("gob", "gate"), ("gob2", "gate"))
    state.creatures["gob2"].hp = 10
    cast(state, "w", "color-spray", ScriptedRng(5, 5, 5, 5, 5, 5))  # pool 30: 10, then 30 > 20
    assert conditions_of(state, "gob2") == ["blinded"] and conditions_of(state, "gob") == []
    assert state.creatures["gob2"].conditions[0].rounds_left == 2


def test_golden_spell_fog_cloud() -> None:
    # Fog Cloud: a heavily obscured area (BG3: blinded inside) for up to an hour, concentration.
    wiz = caster("w", "wizard", spells=["fog-cloud"], slots={1: 1})
    state = battle(wiz, ("gob", "yard"))
    cast(state, "w", "fog-cloud", ScriptedRng(), zone="yard")
    assert conditions_of(state, "gob") == ["blinded"]
    assert state.encounter is not None
    fog = state.encounter.zone_map.zone("yard").surfaces[0]
    assert (fog.kind, fog.concentration, fog.rounds_left) == ("fog", True, 600)


def test_golden_spell_expeditious_retreat() -> None:
    # Expeditious Retreat: bonus action, concentration; Dash as a bonus action on each turn.
    wiz = caster("w", "wizard", spells=["expeditious-retreat"], slots={1: 1})
    state = battle(wiz, ("gob", "yard"))
    cast(state, "w", "expeditious-retreat", ScriptedRng())
    assert conditions_of(state, "w") == ["expeditious-retreat"]
    fresh = fresh_economy(state.creatures["w"])
    apply(state, EconomyChanged(creature_id="w", economy=fresh, reason="next turn"))
    do(state, DashCommand(actor_id="w", bonus_action=True), ScriptedRng())
    assert economy(state, "w").movement_left == 2 * state.creatures["w"].speed
    assert economy(state, "w").action
