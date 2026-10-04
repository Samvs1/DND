"""Every vendored SRD entry validates against its typed model; spot goldens.

Numbers come from the SRD 5.1 (CC-BY-4.0) as vendored in data/srd (5e-bits 2014).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from aidm.data.registry import Registry, UnknownEntryError
from aidm.data.srd import SrdData, load_srd, srd
from aidm.data.srd_characters import (
    SrdBackground,
    SrdClass,
    SrdCondition,
    SrdDamageType,
    SrdFeature,
    SrdLevel,
    SrdProficiency,
    SrdRace,
    SrdSkill,
    SrdSubclass,
    SrdSubrace,
    SrdTrait,
)
from aidm.data.srd_equipment import SrdEquipment
from aidm.data.srd_spells import SrdSpell

SRD_DIR = Path(__file__).resolve().parents[3] / "data" / "srd"

KINDS: list[tuple[str, str, type[BaseModel]]] = [
    ("spells", "spells", SrdSpell),
    ("equipment", "equipment", SrdEquipment),
    ("races", "races", SrdRace),
    ("subraces", "subraces", SrdSubrace),
    ("classes", "classes", SrdClass),
    ("levels", "levels", SrdLevel),
    ("subclasses", "subclasses", SrdSubclass),
    ("features", "features", SrdFeature),
    ("traits", "traits", SrdTrait),
    ("conditions", "conditions", SrdCondition),
    ("skills", "skills", SrdSkill),
    ("damage_types", "damage_types", SrdDamageType),
    ("proficiencies", "proficiencies", SrdProficiency),
    ("backgrounds", "backgrounds", SrdBackground),
]


@pytest.fixture(scope="module")
def data() -> SrdData:
    return load_srd()


@pytest.mark.parametrize(("attr", "stem", "model"), KINDS, ids=[k[0] for k in KINDS])
def test_every_entry_validates(data: SrdData, attr: str, stem: str, model: type[BaseModel]) -> None:
    raw = json.loads((SRD_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    registry = getattr(data, attr)
    assert len(registry) == len(raw) > 0
    assert all(isinstance(e, model) for e in registry.all())


def test_default_srd_is_cached() -> None:
    assert srd() is srd()


def test_golden_fireball(data: SrdData) -> None:
    # SRD 5.1 Spells: Fireball, 3rd-level evocation, 8d6 fire, DEX save for half.
    sp = data.spells.get("fireball")
    assert sp.level == 3
    assert sp.school.index == "evocation"
    assert sp.damage[0].damage_type is not None
    assert sp.damage[0].damage_type.index == "fire"
    assert sp.damage[0].damage_at_slot_level["3"] == "8d6"
    assert sp.dc is not None
    assert sp.dc.dc_type.index == "dex"
    assert sp.dc.dc_success == "half"
    assert sp.area_of_effect is not None
    assert (sp.area_of_effect.type, sp.area_of_effect.size) == ("sphere", 20)


def test_golden_fire_bolt_cantrip_scaling(data: SrdData) -> None:
    # SRD 5.1: Fire Bolt 1d10, 2d10 at 5th, 3d10 at 11th, 4d10 at 17th character level.
    sp = data.spells.get("fire-bolt")
    assert sp.level == 0
    assert sp.damage[0].damage_at_character_level == {
        "1": "1d10",
        "5": "2d10",
        "11": "3d10",
        "17": "4d10",
    }


def test_golden_longsword(data: SrdData) -> None:
    # SRD 5.1 Equipment: Longsword 1d8 slashing, versatile (1d10).
    w = data.equipment.get("longsword")
    assert w.damage is not None
    assert (w.damage.damage_dice, w.damage.damage_type.index) == ("1d8", "slashing")
    assert [p.index for p in w.properties] == ["versatile"]
    assert w.two_handed_damage is not None
    assert w.two_handed_damage.damage_dice == "1d10"


def test_golden_chain_mail(data: SrdData) -> None:
    # SRD 5.1 Equipment: Chain Mail AC 16, no Dex bonus, Str 13, stealth disadvantage.
    a = data.equipment.get("chain-mail")
    assert a.armor_class is not None
    assert a.armor_class.base == 16
    assert a.armor_class.dex_bonus is False
    assert a.str_minimum == 13
    assert a.stealth_disadvantage is True


def test_golden_dwarf_and_hill_dwarf(data: SrdData) -> None:
    # SRD 5.1 Races: Dwarf Con +2, speed 25; Hill Dwarf Wis +1.
    dwarf = data.races.get("dwarf")
    assert dwarf.speed == 25
    assert [(b.ability_score.index, b.bonus) for b in dwarf.ability_bonuses] == [("con", 2)]
    hill = data.subraces.get("hill-dwarf")
    assert hill.race.index == "dwarf"
    assert [(b.ability_score.index, b.bonus) for b in hill.ability_bonuses] == [("wis", 1)]


def test_golden_wizard(data: SrdData) -> None:
    # SRD 5.1 Classes: Wizard hit die d6, saving throws Intelligence and Wisdom.
    wiz = data.classes.get("wizard")
    assert wiz.hit_die == 6
    assert [s.index for s in wiz.saving_throws] == ["int", "wis"]


def test_golden_fighter_level_5(data: SrdData) -> None:
    # SRD 5.1 Fighter table: level 5 proficiency bonus +3, Extra Attack.
    lv = data.levels.get("fighter-5")
    assert lv.level == 5
    assert lv.prof_bonus == 3
    assert lv.class_ref.index == "fighter"
    assert [f.index for f in lv.features] == ["extra-attack-1"]


def test_golden_skills(data: SrdData) -> None:
    # SRD 5.1: 18 skills; Stealth uses Dexterity.
    assert len(data.skills) == 18
    assert data.skills.get("stealth").ability_score.index == "dex"


def test_golden_conditions(data: SrdData) -> None:
    # SRD 5.1 Appendix PH-A: 15 conditions.
    assert len(data.conditions) == 15
    assert "prone" in data.conditions


class _Item(BaseModel):
    index: str


def test_registry_get_find_filter() -> None:
    reg = Registry([_Item(index="a"), _Item(index="b")])
    assert reg.get("a").index == "a"
    assert reg.find("zzz") is None
    assert "b" in reg
    assert "c" not in reg
    assert len(reg) == 2
    assert [e.index for e in reg.all()] == ["a", "b"]
    assert [e.index for e in reg.filter(lambda e: e.index == "b")] == ["b"]


def test_registry_missing_raises_with_index() -> None:
    reg = Registry([_Item(index="a")])
    with pytest.raises(UnknownEntryError) as info:
        reg.get("nope")
    assert isinstance(info.value, KeyError)
    assert info.value.index == "nope"


def test_registry_duplicate_raises() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        Registry([_Item(index="a"), _Item(index="a")])


def test_srd_entries_are_frozen(data: SrdData) -> None:
    with pytest.raises(ValueError, match="frozen"):
        data.skills.get("stealth").name = "x"
