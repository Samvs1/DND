"""Golden and unit tests for aidm.rules.defense (AC) and aidm.rules.hp (HP by level, temp HP).

Numbers come from SRD 5.1 (CC-BY-4.0): "Armor and Shields" table, Barbarian and Monk
"Unarmored Defense", the Mage Armor spell, and the class "Hit Points" blocks.
"""

from __future__ import annotations

import pytest

from aidm.data.ac_formulas import ac_formulas
from aidm.data.srd import srd
from aidm.data.srd_equipment import SrdEquipment
from aidm.models.abilities import Ability
from aidm.models.events import TempHpSet
from aidm.models.state import Creature, CreatureKind
from aidm.rules.defense import armor_class, armor_formula, shield_bonus
from aidm.rules.hp import gain_temp_hp, hp_gain_at_level_up, max_hp_at_level


def scores(**kw: int) -> dict[Ability, int]:
    base = dict.fromkeys(Ability, 10)
    base.update({Ability(k): v for k, v in kw.items()})
    return base


def eq(index: str) -> SrdEquipment:
    return srd().equipment.get(index)


def test_golden_armor_table() -> None:
    # SRD 5.1 Armor table: leather 11 + Dex; half plate 15 + Dex (max 2); chain mail 16.
    assert armor_class(scores(dex=16), armor=eq("leather-armor")) == 14
    assert armor_class(scores(dex=18), armor=eq("half-plate-armor")) == 17
    assert armor_class(scores(dex=8), armor=eq("half-plate-armor")) == 14
    assert armor_class(scores(dex=18), armor=eq("chain-mail")) == 16
    assert armor_class(scores(dex=6), armor=eq("plate-armor")) == 18


def test_golden_shield_and_unarmored() -> None:
    # SRD 5.1: shield +2; no armor = 10 + Dex.
    assert shield_bonus(eq("shield")) == 2
    assert armor_class(scores(dex=14)) == 12
    assert armor_class(scores(dex=14), shield=eq("shield")) == 14
    assert armor_class(scores(), armor=eq("chain-mail"), shield=eq("shield")) == 18


def test_golden_barbarian_unarmored_defense() -> None:
    # SRD 5.1 Barbarian: 10 + Dex + Con without armor; a shield still applies.
    ud = [ac_formulas().get("unarmored-defense-barbarian")]
    abil = scores(dex=14, con=16)
    assert armor_class(abil, formulas=ud) == 15
    assert armor_class(abil, formulas=ud, shield=eq("shield")) == 17
    # Wearing armor disables it: hide 12 + Dex 2.
    assert armor_class(abil, formulas=ud, armor=eq("hide-armor")) == 14


def test_golden_monk_unarmored_defense() -> None:
    # SRD 5.1 Monk: 10 + Dex + Wis without armor AND without a shield.
    ud = [ac_formulas().get("unarmored-defense-monk")]
    abil = scores(dex=16, wis=16)
    assert armor_class(abil, formulas=ud) == 16
    assert armor_class(abil, formulas=ud, shield=eq("shield")) == 15


def test_golden_mage_armor_and_best_formula() -> None:
    # SRD 5.1 Mage Armor: base AC 13 + Dex if the target wears no armor.
    reg = ac_formulas()
    ma = [reg.get("mage-armor")]
    assert armor_class(scores(dex=14), formulas=ma) == 15
    assert armor_class(scores(dex=14), formulas=ma, armor=eq("leather-armor")) == 13
    both = [reg.get("unarmored-defense-barbarian"), reg.get("mage-armor")]
    assert armor_class(scores(dex=16, con=10), formulas=both) == 16
    assert armor_class(scores(dex=16, con=18), formulas=both, bonus=1) == 18


def test_formulas_registry_and_bad_items() -> None:
    assert len(ac_formulas()) == 3
    with pytest.raises(ValueError):
        armor_formula(eq("shield"))
    with pytest.raises(ValueError):
        armor_formula(eq("longsword"))
    with pytest.raises(ValueError):
        shield_bonus(eq("leather-armor"))


def test_golden_hp_by_level() -> None:
    # SRD 5.1 Fighter: 10 + Con at 1st level, then 6 (fixed) + Con per level.
    assert max_hp_at_level(10, 2, 1) == 12
    assert max_hp_at_level(10, 2, 5) == 44
    # SRD 5.1 Wizard: 6 + Con, then 4 + Con. Barbarian: 12 + Con, then 7 + Con.
    assert max_hp_at_level(6, 0, 5) == 22
    assert max_hp_at_level(12, 3, 3) == 35
    assert hp_gain_at_level_up(8, 1) == 6


def test_hp_minimum_one_per_level_and_validation() -> None:
    assert max_hp_at_level(6, -5, 1) == 1
    assert max_hp_at_level(6, -5, 4) == 4
    with pytest.raises(ValueError):
        max_hp_at_level(7, 0, 1)
    with pytest.raises(ValueError):
        max_hp_at_level(8, 0, 0)


def test_temp_hp_do_not_stack_keep_higher() -> None:
    # SRD 5.1 "Temporary Hit Points": they don't stack; choose which to keep.
    c = Creature(id="a", name="A", kind=CreatureKind.PC, max_hp=10, hp=10, temp_hp=5)
    assert gain_temp_hp(c, 3) == []
    assert gain_temp_hp(c, 5) == []
    assert gain_temp_hp(c, 8) == [TempHpSet(creature_id="a", temp_hp=8)]
    with pytest.raises(ValueError):
        gain_temp_hp(c, -1)
