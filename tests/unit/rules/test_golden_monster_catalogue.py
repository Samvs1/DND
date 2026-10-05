"""Golden tests for the M3.9 monster catalogue: AC, HP, to-hit, damage and save DC of each
monster's signature action. Every number is copied from the SRD 5.1 stat block (CC-BY-4.0, as
vendored in data/srd/monsters.json, 5e-bits 2014) and cited per test."""

from __future__ import annotations

from aidm.data.encounter_monsters import encounter_monsters
from aidm.models.combat import AttackProfile
from aidm.models.combat_events import MonsterActionUsed
from aidm.models.encounter import Side
from aidm.models.events import CheckResolved
from aidm.rules.monster_catalog import MonsterCatalog, MonsterOption, monster_catalog
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, fight
from tests.unit.rules.monster_fixtures import act, dummy, hp, srd_monster
from tests.unit.rules.spell_fixtures import of


def _catalog(index: str) -> MonsterCatalog:
    return monster_catalog(REGS.monsters.get(index), REGS.monster_overlay, REGS.spells)


def _option(index: str, key: str) -> MonsterOption:
    option = _catalog(index).option(key)
    assert option is not None, key
    return option


def _melee(index: str, key: str) -> AttackProfile:
    melee = _option(index, key).melee
    assert melee is not None, key
    return melee


def _ranged(index: str, key: str) -> AttackProfile:
    ranged = _option(index, key).ranged
    assert ranged is not None, key
    return ranged


def _stats(index: str) -> tuple[int, int]:
    creature = srd_monster(index, "m")
    assert index in encounter_monsters()
    return creature.ac, creature.max_hp


def _numbers(profile: AttackProfile) -> tuple[int, str, str]:
    return profile.attack_bonus, profile.damage, profile.damage_type.value


def _extra(profile: AttackProfile) -> list[tuple[str, str]]:
    return [(p.dice, p.damage_type.value) for p in profile.extra_damage]


def test_golden_monster_wolf_bite() -> None:
    # SRD Wolf: AC 13, 11 (2d8+2) hp; Bite +4, 7 (2d4+2) piercing, DC 11 Str save or prone (the
    # last scripted 20 passes it).
    assert _stats("wolf") == (13, 11)
    assert _numbers(_melee("wolf", "bite")) == (4, "2d4+2", "piercing")
    state = fight(
        [
            (srd_monster("wolf", "w"), Side.HOSTILE, "gate"),
            (dummy("t", ac=12), Side.PARTY, "gate"),
        ]
    )
    events = act(state, "w", "bite", ScriptedRng(10, 3, 4, 20), targets=["t"])
    assert hp(state, "t") == 100 - (3 + 4 + 2)
    assert of(events, MonsterActionUsed)[0].action == "bite"


def test_golden_monster_bandit_scimitar_and_crossbow() -> None:
    # SRD Bandit: AC 12 (leather), 11 (2d8+2) hp; Scimitar +3 1d6+1 slashing; Light Crossbow
    # +3 1d8+1 piercing, range 80/320.
    assert _stats("bandit") == (12, 11)
    assert _numbers(_melee("bandit", "scimitar")) == (3, "1d6+1", "slashing")
    crossbow = _ranged("bandit", "light-crossbow")
    assert _numbers(crossbow) == (3, "1d8+1", "piercing")
    assert (crossbow.range_normal, crossbow.range_long) == (80, 320)


def test_golden_monster_kobold_dagger() -> None:
    # SRD Kobold: AC 12, 5 (2d6-2) hp; Dagger +4, 4 (1d4+2) piercing; Sling +4, 4 (1d4+2)
    # bludgeoning.
    assert _stats("kobold") == (12, 5)
    assert _numbers(_melee("kobold", "dagger")) == (4, "1d4+2", "piercing")
    assert _numbers(_ranged("kobold", "sling")) == (4, "1d4+2", "bludgeoning")


def test_golden_monster_orc_greataxe() -> None:
    # SRD Orc: AC 13 (hide armor), 15 (2d8+6) hp; Greataxe +5, 9 (1d12+3) slashing.
    assert _stats("orc") == (13, 15)
    assert _numbers(_melee("orc", "greataxe")) == (5, "1d12+3", "slashing")


def test_golden_monster_gnoll_spear_and_bite() -> None:
    # SRD Gnoll: AC 15 (hide armor, shield), 22 (5d8) hp; Bite +4 1d4+2 piercing; Spear +4 1d6+2
    # piercing; Longbow +3 1d8+1 piercing.
    assert _stats("gnoll") == (15, 22)
    assert _numbers(_melee("gnoll", "bite")) == (4, "1d4+2", "piercing")
    assert _numbers(_melee("gnoll", "spear")) == (4, "1d6+2", "piercing")
    assert _numbers(_ranged("gnoll", "longbow")) == (3, "1d8+1", "piercing")


def test_golden_monster_bugbear_morningstar() -> None:
    # SRD Bugbear: AC 16 (hide armor, shield), 27 (5d8+5) hp; Morningstar +4, 11 (2d8+2)
    # piercing.
    assert _stats("bugbear") == (16, 27)
    assert _numbers(_melee("bugbear", "morningstar")) == (4, "2d8+2", "piercing")


def test_golden_monster_veteran_multiattack() -> None:
    # SRD Veteran: AC 17 (splint), 58 (9d8+18) hp; Multiattack: two longsword attacks and one
    # shortsword attack. Longsword +5 1d8+3 slashing; Shortsword +5 1d6+3 piercing.
    assert _stats("veteran") == (17, 58)
    assert _numbers(_melee("veteran", "longsword")) == (5, "1d8+3", "slashing")
    assert _numbers(_melee("veteran", "shortsword")) == (5, "1d6+3", "piercing")
    steps = [s.action for s in _option("veteran", "multiattack").routines[0]]
    assert steps.count("longsword") == 2 and "shortsword" in steps


def test_golden_monster_black_dragon_wyrmling_acid_breath() -> None:
    # SRD Black Dragon Wyrmling: AC 17, 33 (6d8+6) hp; Bite +4 1d10+2 piercing plus 1d4 acid;
    # Acid Breath (Recharge 5-6) 15-ft line, DC 11 Dex, 22 (5d8) acid, half on a success.
    assert _stats("black-dragon-wyrmling") == (17, 33)
    bite = _melee("black-dragon-wyrmling", "bite")
    assert _numbers(bite) == (4, "1d10+2", "piercing")
    assert _extra(bite) == [("1d4", "acid")]
    assert _option("black-dragon-wyrmling", "acid-breath").dc == 11
    state = fight(
        [
            (srd_monster("black-dragon-wyrmling", "d"), Side.HOSTILE, "gate"),
            (dummy("t"), Side.PARTY, "gate"),
        ]
    )
    events = act(state, "d", "acid-breath", ScriptedRng(5, 4, 4, 4, 4, 4), targets=["t"])
    assert [(s.result.dc, s.result.success) for s in of(events, CheckResolved)] == [(11, False)]
    assert hp(state, "t") == 100 - 20


def test_golden_monster_blue_dragon_wyrmling_lightning_breath() -> None:
    # SRD Blue Dragon Wyrmling: AC 17, 52 (8d8+16) hp; Bite +5 1d10+3 piercing plus 1d6
    # lightning; Lightning Breath (Recharge 5-6) 30-ft line, DC 12 Dex, 22 (4d10) lightning.
    assert _stats("blue-dragon-wyrmling") == (17, 52)
    bite = _melee("blue-dragon-wyrmling", "bite")
    assert _numbers(bite) == (5, "1d10+3", "piercing")
    assert _extra(bite) == [("1d6", "lightning")]
    breath = _option("blue-dragon-wyrmling", "lightning-breath")
    assert breath.dc == 12 and breath.resource is not None


def test_golden_monster_young_black_dragon_multiattack_and_breath() -> None:
    # SRD Young Black Dragon: AC 18, 127 (15d10+45) hp; Multiattack bite + 2 claws; Bite +7
    # 2d10+4 piercing + 1d8 acid; Claw +7 2d6+4 slashing; Acid Breath DC 14 Dex, 49 (11d8).
    assert _stats("young-black-dragon") == (18, 127)
    assert _numbers(_melee("young-black-dragon", "bite")) == (7, "2d10+4", "piercing")
    assert _numbers(_melee("young-black-dragon", "claw")) == (7, "2d6+4", "slashing")
    multi = _option("young-black-dragon", "multiattack")
    assert [s.action for s in multi.routines[0]] == ["bite", "claw", "claw"]
    assert _option("young-black-dragon", "acid-breath").dc == 14


def test_golden_monster_troll_claws() -> None:
    # SRD Troll: AC 15 (natural armor), 84 (8d10+40) hp; Multiattack bite + 2 claws; Bite +7
    # 1d6+4 piercing; Claw +7 2d6+4 slashing. Regeneration is an inert trait (DECISIONS M3.8).
    assert _stats("troll") == (15, 84)
    assert _numbers(_melee("troll", "bite")) == (7, "1d6+4", "piercing")
    assert _numbers(_melee("troll", "claw")) == (7, "2d6+4", "slashing")
    multi = _option("troll", "multiattack")
    assert [s.action for s in multi.routines[0]] == ["bite", "claw", "claw"]


def test_golden_monster_hell_hound_fire_breath() -> None:
    # SRD Hell Hound: AC 15 (natural armor), 45 (7d8+14) hp; Bite +5 1d8+3 piercing plus 2d6
    # fire; Fire Breath (Recharge 5-6) 15-ft cone, DC 12 Dex, 21 (6d6) fire.
    assert _stats("hell-hound") == (15, 45)
    bite = _melee("hell-hound", "bite")
    assert _numbers(bite) == (5, "1d8+3", "piercing")
    assert _extra(bite) == [("2d6", "fire")]
    assert _option("hell-hound", "fire-breath").dc == 12


def test_golden_monster_gladiator_routines() -> None:
    # SRD Gladiator: AC 16 (studded leather, shield), 112 (15d8+45) hp; Multiattack three melee
    # attacks or two ranged; Spear +7 2d6+4 piercing; Shield Bash +7 2d4+4 bludgeoning.
    assert _stats("gladiator") == (16, 112)
    assert _numbers(_melee("gladiator", "spear")) == (7, "2d6+4", "piercing")
    assert _numbers(_melee("gladiator", "shield-bash")) == (7, "2d4+4", "bludgeoning")
    routines = _option("gladiator", "multiattack").routines
    assert any(len(r) == 2 and all(s.mode == "ranged" for s in r) for r in routines)
    assert any(len(r) == 3 for r in routines)


def test_golden_monster_manticore_tail_spikes() -> None:
    # SRD Manticore: AC 14 (natural armor), 68 (8d10+24) hp; Multiattack bite + 2 claws, or
    # three Tail Spikes; Tail Spike +5, 1d8+3 piercing, range 100/200 ft.
    assert _stats("manticore") == (14, 68)
    spike = _ranged("manticore", "tail-spike")
    assert _numbers(spike) == (5, "1d8+3", "piercing")
    assert (spike.range_normal, spike.range_long) == (100, 200)
    assert len(_option("manticore", "multiattack").routines) == 2


def test_golden_monster_cult_fanatic_spell_kit() -> None:
    # SRD Cult Fanatic: AC 13 (leather), 22 (6d8-6) hp; Multiattack two melee attacks; Dagger +4
    # 1d4+2 piercing; Spellcasting (4th-level caster, spell save DC 11, +3 to hit).
    assert _stats("cult-fanatic") == (13, 22)
    assert _numbers(_melee("cult-fanatic", "dagger")) == (4, "1d4+2", "piercing")
    multi = _option("cult-fanatic", "multiattack")
    assert [s.action for s in multi.routines[0]] == ["dagger", "dagger"]
    wounds = _catalog("cult-fanatic").spell("inflict-wounds")
    assert wounds is not None and (wounds.save_dc, wounds.attack_bonus) == (11, 3)
