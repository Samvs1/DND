"""Armor Class from equipment and AC formulas.

Public API:
- `UNARMORED_FORMULA`: 10 + DEX (SRD 5.1 "Armor Class": without armor, AC is 10 + DEX modifier).
- `armor_formula(armor) -> AcFormula`: an SRD armor entry as a formula. Light armor: base + DEX;
  medium: base + DEX capped by `max_bonus` (2); heavy (`dex_bonus` false): base only
  (SRD 5.1 "Armor and Shields"). Raises ValueError for a shield or a non-armor item.
- `shield_bonus(shield) -> int`: the SRD shield entry's AC bonus (+2). ValueError if not a shield.
- `formula_value(formula, abilities) -> int`: base + the listed ability modifiers (DEX capped).
- `armor_class(abilities, *, armor=None, shield=None, formulas=(), bonus=0) -> int`: the best
  applicable formula, plus the shield, plus flat `bonus` (magic items, Shield of Faith).
  Candidates: worn armor's formula (or `UNARMORED_FORMULA`), and every supplied formula
  (Unarmored Defense, Mage Armor from data/bg3/ac_formulas.json) that is allowed: one with
  `requires_unarmored` needs no body armor, one with `forbids_shield` needs no shield. Taking the
  best is the SRD rule for competing base-AC calculations (only one applies; you choose).
"""

from collections.abc import Iterable, Mapping

from aidm.data.ac_formulas import AcFormula
from aidm.data.srd_equipment import SrdEquipment
from aidm.models.abilities import Ability
from aidm.rules.abilities import ability_modifier

SHIELD_CATEGORY = "Shield"

UNARMORED_FORMULA = AcFormula(index="unarmored", name="Unarmored", base=10, abilities=("dex",))


def armor_formula(armor: SrdEquipment) -> AcFormula:
    ac = armor.armor_class
    if ac is None or armor.armor_category in (None, SHIELD_CATEGORY):
        raise ValueError(f"{armor.index!r} is not body armor")
    return AcFormula(
        index=armor.index,
        name=armor.name,
        base=ac.base,
        abilities=("dex",) if ac.dex_bonus else (),
        dex_cap=ac.max_bonus,
    )


def shield_bonus(shield: SrdEquipment) -> int:
    if shield.armor_class is None or shield.armor_category != SHIELD_CATEGORY:
        raise ValueError(f"{shield.index!r} is not a shield")
    return shield.armor_class.base


def formula_value(formula: AcFormula, abilities: Mapping[Ability, int]) -> int:
    total = formula.base
    for key in formula.abilities:
        ability = Ability(key)
        mod = ability_modifier(abilities[ability])
        if ability is Ability.DEX and formula.dex_cap is not None:
            mod = min(mod, formula.dex_cap)
        total += mod
    return total


def armor_class(
    abilities: Mapping[Ability, int],
    *,
    armor: SrdEquipment | None = None,
    shield: SrdEquipment | None = None,
    formulas: Iterable[AcFormula] = (),
    bonus: int = 0,
) -> int:
    candidates = [armor_formula(armor) if armor is not None else UNARMORED_FORMULA]
    for formula in formulas:
        if formula.requires_unarmored and armor is not None:
            continue
        if formula.forbids_shield and shield is not None:
            continue
        candidates.append(formula)
    best = max(formula_value(f, abilities) for f in candidates)
    extra = shield_bonus(shield) if shield is not None else 0
    return best + extra + bonus
