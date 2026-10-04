"""Every vendored SRD monster validates; goldens for the parts v1 dropped.

Numbers come from the SRD 5.1 (CC-BY-4.0) as vendored in data/srd/monsters.json
(5e-bits 2014). Where the JSON differs from SRD print, the JSON is trusted and
the difference is noted in a comment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidm.data.srd import SrdData, load_srd
from aidm.data.srd_monsters import SrdMonster

SRD_DIR = Path(__file__).resolve().parents[3] / "data" / "srd"


@pytest.fixture(scope="module")
def data() -> SrdData:
    return load_srd()


def test_every_monster_validates(data: SrdData) -> None:
    raw = json.loads((SRD_DIR / "monsters.json").read_text(encoding="utf-8"))
    assert len(data.monsters) == len(raw) == 334
    assert all(isinstance(m, SrdMonster) for m in data.monsters.all())


def test_nothing_dropped_corpus_wide(data: SrdData) -> None:
    # The v1 library lost breath DCs, legendary actions and spell kits.
    raw = json.loads((SRD_DIR / "monsters.json").read_text(encoding="utf-8"))
    raw_casters = sum(
        1 for m in raw if any("spellcasting" in s for s in m.get("special_abilities", []))
    )
    raw_legendary = sum(1 for m in raw if m.get("legendary_actions"))
    raw_dc_actions = sum(1 for m in raw for a in m.get("actions", []) if "dc" in a)
    mons = data.monsters.all()
    assert sum(m.is_spellcaster for m in mons) == raw_casters
    assert sum(bool(m.legendary_actions) for m in mons) == raw_legendary
    assert sum(1 for m in mons for a in m.actions if a.dc is not None) == raw_dc_actions
    assert raw_casters > 0
    assert raw_legendary > 0


def test_golden_monster_adult_red_dragon(data: SrdData) -> None:
    # SRD 5.1 Adult Red Dragon: AC 19, HP 256 (19d12+133), CR 17, Fire Breath
    # (Recharge 5-6) DC 21 Dex save, 63 (18d6) fire. The vendored JSON lists
    # the breath success_type as "none" (SRD print: half on a save); trust JSON.
    m = data.monsters.get("adult-red-dragon")
    assert (m.ac, m.hit_points, m.cr, m.xp) == (19, 256, 17.0, 18000)
    breath = m.breath_weapons
    assert [b.name for b in breath] == ["Fire Breath"]
    assert breath[0].dc is not None
    assert (breath[0].dc.dc_type.index, breath[0].dc.dc_value) == ("dex", 21)
    assert breath[0].damage[0].damage_dice == "18d6"
    assert breath[0].damage[0].damage_type is not None
    assert breath[0].damage[0].damage_type.index == "fire"
    assert breath[0].usage is not None
    assert (breath[0].usage.type, breath[0].usage.dice, breath[0].usage.min_value) == (
        "recharge on roll",
        "1d6",
        5,
    )
    multi = m.actions[0]
    assert multi.name == "Multiattack"
    assert multi.multiattack_type == "actions"
    assert [(p.action_name, p.count) for p in multi.actions] == [
        ("Frightful Presence", 1),
        ("Bite", 1),
        ("Claw", 2),
    ]
    assert [la.name for la in m.legendary_actions] == [
        "Detect",
        "Tail Attack",
        "Wing Attack (Costs 2 Actions)",
    ]
    assert m.save_bonus("dex") == 6
    assert m.damage_immunities == ["fire"]


def test_golden_monster_young_green_dragon(data: SrdData) -> None:
    # SRD 5.1 Young Green Dragon: AC 18, HP 136, CR 8, Poison Breath
    # (Recharge 5-6) DC 14 Con save, 42 (12d6) poison, half on a save.
    m = data.monsters.get("young-green-dragon")
    assert (m.ac, m.hit_points, m.cr) == (18, 136, 8.0)
    (breath,) = m.breath_weapons
    assert breath.name == "Poison Breath"
    assert breath.dc is not None
    assert (breath.dc.dc_type.index, breath.dc.dc_value, breath.dc.success_type) == (
        "con",
        14,
        "half",
    )
    assert breath.damage[0].damage_dice == "12d6"
    assert breath.usage is not None
    assert breath.usage.min_value == 5
    assert [c.index for c in m.condition_immunities] == ["poisoned"]


def test_golden_monster_young_white_dragon(data: SrdData) -> None:
    # SRD 5.1 Young White Dragon: CR 6, Cold Breath (Recharge 5-6) DC 15 Con
    # save, 45 (10d8) cold in a 30-foot cone.
    m = data.monsters.get("young-white-dragon")
    assert (m.cr, m.hit_points, m.ac) == (6.0, 133, 17)
    (breath,) = m.breath_weapons
    assert breath.dc is not None
    assert (breath.dc.dc_type.index, breath.dc.dc_value) == ("con", 15)
    assert breath.damage[0].damage_dice == "10d8"
    assert breath.usage is not None
    assert breath.usage.min_value == 5


def test_golden_monster_adult_brass_dragon_option_breaths(data: SrdData) -> None:
    # SRD 5.1 Adult Brass Dragon: Fire Breath DC 18 Dex 13d6 fire OR Sleep
    # Breath DC 18 Con, kept from the nested `options` blob, shared recharge 5-6.
    m = data.monsters.get("adult-brass-dragon")
    by_name = {b.name: b for b in m.breath_weapons}
    assert set(by_name) == {"Fire Breath", "Sleep Breath"}
    fire = by_name["Fire Breath"]
    assert fire.dc is not None
    assert (fire.dc.dc_type.index, fire.dc.dc_value) == ("dex", 18)
    assert fire.damage[0].damage_dice == "13d6"
    sleep = by_name["Sleep Breath"]
    assert sleep.dc is not None
    assert (sleep.dc.dc_type.index, sleep.dc.dc_value) == ("con", 18)
    assert sleep.usage is not None
    assert sleep.usage.min_value == 5


def test_golden_monster_mage(data: SrdData) -> None:
    # SRD 5.1 Mage: CR 6, 40 HP, 9th-level caster, INT, DC 14, +6 to hit;
    # slots 4/3/3/3/1 (level 5: 1); spells include fireball and shield.
    # AC 12 (15 with mage armor) is the listed first value: 12.
    m = data.monsters.get("mage")
    assert (m.cr, m.hit_points, m.ac) == (6.0, 40, 12)
    assert m.is_spellcaster
    sc = m.spellcasting
    assert sc is not None
    assert (sc.ability.index, sc.dc, sc.modifier, sc.level) == ("int", 14, 6, 9)
    assert sc.slots == {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1}
    names = {s.name.lower() for s in sc.spells}
    assert {"fireball", "shield", "cone of cold", "fire bolt"} <= names
    fireball = next(s for s in sc.spells if s.name == "Fireball")
    assert (fireball.level, fireball.url) == (3, "/api/2014/spells/fireball")
    assert [a.type for a in m.armor_class] == ["dex", "spell"]
    assert m.armor_class[1].spell is not None
    assert m.armor_class[1].spell.index == "mage-armor"
    assert m.save_bonus("int") == 6


def test_golden_monster_priest(data: SrdData) -> None:
    # SRD 5.1 Priest: CR 2, 27 HP, 5th-level cleric, WIS DC 13, +5 to hit,
    # slots 4/3/2 with spiritual weapon and spirit guardians.
    m = data.monsters.get("priest")
    assert (m.cr, m.hit_points) == (2.0, 27)
    sc = m.spellcasting
    assert sc is not None
    assert (sc.ability.index, sc.dc, sc.modifier, sc.level) == ("wis", 13, 5, 5)
    assert sc.slots == {"1": 4, "2": 3, "3": 2}
    assert {"Spiritual Weapon", "Spirit Guardians"} <= {s.name for s in sc.spells}


def test_golden_monster_lich_legendary_and_slots(data: SrdData) -> None:
    # SRD 5.1 Lich: CR 21, 18th-level wizard (INT DC 20, +12), slots through
    # 9th (1 each), 4 legendary actions, resistant to cold/lightning/necrotic.
    m = data.monsters.get("lich")
    assert m.cr == 21.0
    sc = m.spellcasting
    assert sc is not None
    assert (sc.dc, sc.modifier, sc.slots["9"]) == (20, 12, 1)
    assert [la.name for la in m.legendary_actions][:3] == [
        "Cantrip",
        "Paralyzing Touch (Costs 2 Actions)",
        "Frightening Gaze (Costs 2 Actions)",
    ]
    assert len(m.legendary_actions) == 4
    gaze = m.legendary_actions[2]
    assert gaze.dc is not None
    assert (gaze.dc.dc_type.index, gaze.dc.dc_value) == ("wis", 18)
    assert m.damage_resistances == ["cold", "lightning", "necrotic"]


def test_golden_monster_owlbear(data: SrdData) -> None:
    # SRD 5.1 Owlbear: AC 13, 59 HP, CR 3; Multiattack = one beak and one
    # claws (Beak 1d10+5 piercing, Claws 2d8+5 slashing, +7 to hit).
    m = data.monsters.get("owlbear")
    assert (m.ac, m.hit_points, m.cr) == (13, 59, 3.0)
    multi = m.actions[0]
    assert [(p.action_name, p.count, p.type) for p in multi.actions] == [
        ("Beak", 1, "melee"),
        ("Claws", 1, "melee"),
    ]
    beak = next(a for a in m.actions if a.name == "Beak")
    assert beak.attack_bonus == 7
    assert beak.damage[0].damage_dice == "1d10+5"
    claws = next(a for a in m.actions if a.name == "Claws")
    assert claws.damage[0].damage_dice == "2d8+5"


def test_golden_monster_goblin(data: SrdData) -> None:
    # SRD 5.1 Goblin: AC 15 (leather armor, shield), 7 HP, CR 1/4,
    # Nimble Escape (Disengage or Hide as a bonus action).
    m = data.monsters.get("goblin")
    assert (m.ac, m.hit_points, m.cr, m.xp) == (15, 7, 0.25, 50)
    assert [a.name for a in m.special_abilities] == ["Nimble Escape"]
    assert [r.index for r in m.armor_class[0].armor] == ["leather-armor", "shield"]
    assert m.save_bonus("dex") == 2  # no save proficiency: falls back to DEX mod


def test_golden_monster_hobgoblin(data: SrdData) -> None:
    # SRD 5.1 Hobgoblin: AC 18 (chain mail, shield), 11 HP, CR 1/2,
    # Longsword +3 to hit.
    m = data.monsters.get("hobgoblin")
    assert (m.ac, m.hit_points, m.cr) == (18, 11, 0.5)
    sword = next(a for a in m.actions if a.name == "Longsword")
    assert sword.attack_bonus == 3
    assert not m.is_spellcaster
    assert m.breath_weapons == []


def test_golden_monster_ogre(data: SrdData) -> None:
    # SRD 5.1 Ogre: AC 11 (hide armor), 59 HP, CR 2, Greatclub +6 to hit,
    # 13 (2d8 + 4) bludgeoning. The SRD ogre has no Multiattack.
    m = data.monsters.get("ogre")
    assert (m.ac, m.hit_points, m.cr) == (11, 59, 2.0)
    club = next(a for a in m.actions if a.name == "Greatclub")
    assert club.attack_bonus == 6
    assert club.damage[0].damage_dice == "2d8+4"
    assert club.damage[0].damage_type is not None
    assert club.damage[0].damage_type.index == "bludgeoning"
    assert all(a.name != "Multiattack" for a in m.actions)


def test_golden_monster_bandit_captain(data: SrdData) -> None:
    # SRD 5.1 Bandit Captain: AC 15, 65 HP, CR 2. Multiattack is a choice:
    # two scimitar + one dagger (3 melee parts), or two ranged dagger attacks.
    m = data.monsters.get("bandit-captain")
    assert (m.ac, m.hit_points, m.cr) == (15, 65, 2.0)
    multi = m.actions[0]
    assert multi.multiattack_type == "action_options"
    assert multi.actions == []
    blob = json.dumps(multi.action_options)
    assert blob.count("Scimitar") == 1
    assert '"count": 2' in blob
    assert [r.name for r in m.reactions] == ["Parry"]


def test_golden_monster_ghoul_condition_immunities(data: SrdData) -> None:
    # SRD 5.1 Ghoul: CR 1, 22 HP, immune to poison damage and to the
    # charmed, exhaustion and poisoned conditions.
    m = data.monsters.get("ghoul")
    assert (m.cr, m.hit_points) == (1.0, 22)
    assert m.damage_immunities == ["poison"]
    assert {c.index for c in m.condition_immunities} == {"poisoned", "charmed", "exhaustion"}


def test_golden_monster_wight_resistances(data: SrdData) -> None:
    # SRD 5.1 Wight: CR 3, 45 HP, resistant to necrotic and to nonmagical,
    # non-silvered weapon damage; immune to poison, exhaustion and poisoned.
    m = data.monsters.get("wight")
    assert (m.cr, m.hit_points, m.ac) == (3.0, 45, 14)
    assert m.damage_resistances[0] == "necrotic"
    assert len(m.damage_resistances) == 2
    assert {c.index for c in m.condition_immunities} == {"exhaustion", "poisoned"}


def test_damage_choice_options_are_flattened(data: SrdData) -> None:
    # SRD 5.1 Djinni scimitar: 2d6+5 slashing plus 1d6 lightning OR thunder.
    scimitar = next(a for a in data.monsters.get("djinni").actions if a.name == "Scimitar")
    assert scimitar.damage[0].damage_dice == "2d6+5"
    choice = scimitar.damage[1]
    assert choice.choose == 1
    assert choice.damage_dice is None
    assert [o.damage_type.index for o in choice.options if o.damage_type] == [
        "lightning",
        "thunder",
    ]


def test_save_bonus_uses_proficiency_value(data: SrdData) -> None:
    # SRD 5.1 Adult Red Dragon saves: DEX +6, CON +13, WIS +7, CHA +11.
    m = data.monsters.get("adult-red-dragon")
    assert [m.save_bonus(a) for a in ("dex", "con", "wis", "cha")] == [6, 13, 7, 11]
    assert m.save_bonus("str") == 8  # STR 27 modifier, no proficiency
