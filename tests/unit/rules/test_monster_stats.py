"""SRD stat block -> combat Creature."""

from __future__ import annotations

from aidm.data.srd import srd
from aidm.models.abilities import Ability, Skill
from aidm.models.character import Size
from aidm.models.damage import DamageType
from aidm.models.state import CreatureKind
from aidm.rules.monster_stats import creature_from_monster

M = srd().monsters


def test_golden_goblin() -> None:
    # SRD 5.1 Goblin: Small, AC 15, HP 7, speed 30 ft, DEX 14, Stealth +6, darkvision 60 ft.
    c = creature_from_monster(M.get("goblin"), "goblin-1")
    assert (c.kind, c.name, c.size, c.ac, c.hp, c.max_hp) == (
        CreatureKind.MONSTER,
        "Goblin",
        Size.SMALL,
        15,
        7,
        7,
    )
    assert (c.speed, c.darkvision, c.proficiency_bonus) == (30, 60, 2)
    assert c.skill_proficiencies == [Skill.STEALTH]
    assert c.skill_expertise == [Skill.STEALTH]  # +6 = DEX +2 plus twice PB 2
    assert c.death_saves is None


def test_golden_skeleton_defences() -> None:
    # SRD 5.1 Skeleton: vulnerable bludgeoning, immune poison, immune exhaustion and poisoned.
    c = creature_from_monster(M.get("skeleton"), "s", name="Rattling Guard")
    assert c.name == "Rattling Guard"
    assert c.vulnerabilities == [DamageType.BLUDGEONING]
    assert c.immunities == [DamageType.POISON]
    assert sorted(c.condition_immunities) == ["exhaustion", "poisoned"]


def test_golden_red_dragon_saves() -> None:
    # SRD 5.1 Adult Red Dragon: HP 256, AC 19, saves DEX/CON/WIS/CHA, immune fire, Huge.
    c = creature_from_monster(M.get("adult-red-dragon"), "d")
    assert (c.hp, c.ac, c.size, c.proficiency_bonus) == (256, 19, Size.HUGE, 6)
    assert c.save_proficiencies == [Ability.DEX, Ability.CON, Ability.WIS, Ability.CHA]
    assert c.immunities == [DamageType.FIRE]


def test_nonmagical_weapon_resistance_maps_to_physical_types() -> None:
    # SRD 5.1 Ghost: resists acid, fire, lightning, thunder; B/P/S from nonmagical attacks.
    c = creature_from_monster(M.get("ghost"), "g")
    assert set(c.resistances) == {
        DamageType.ACID,
        DamageType.FIRE,
        DamageType.LIGHTNING,
        DamageType.THUNDER,
        DamageType.BLUDGEONING,
        DamageType.PIERCING,
        DamageType.SLASHING,
    }


def test_flyer_without_walk_speed_uses_its_best_speed() -> None:
    flyers = [m for m in M.all() if not m.speed.walk and m.speed.fly]
    assert flyers
    c = creature_from_monster(flyers[0], "f")
    assert c.speed > 0


def test_every_srd_monster_converts() -> None:
    for monster in M.all():
        c = creature_from_monster(monster, "x")
        assert c.hp == monster.hit_points and c.ac == monster.ac
