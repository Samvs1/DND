"""Weapon attack numbers for a PC's equipped weapons (SPEC 8 sheet; reused by M3.3 attacks).

SRD 5.1 "Making an Attack": attack bonus = ability modifier + proficiency bonus (when proficient);
melee weapons use STR, ranged weapons DEX, finesse weapons the better of the two. Damage = weapon
die + the same modifier; the light off-hand attack adds no positive modifier unless a feature
says so (Two-Weapon Fighting). A versatile weapon held alone with no shield uses its two-handed
die. Feature modifiers (Archery, Dueling) come from `aidm.rules.features`.

Public API:
- `UNARMED_STRIKE_DAMAGE` (1, SRD: 1 + STR modifier bludgeoning).
- `weapon_proficient(pc, weapon, proficiencies) -> bool`: category (simple/martial) or the
  specific SRD weapon proficiency.
- `weapon_attack_ability(creature, weapon) -> Ability`.
- `wields_two_handed(pc, weapon) -> bool`; `attack_context(pc, weapon, hand) -> AttackContext`
  (the static part: ranged, finesse, two-handed, off-hand, second weapon; the combat layer adds
  advantage and target facts).
- `weapon_attack_line(creature, weapon, hand, regs) -> AttackLine`;
  `attack_lines(creature, regs) -> list[AttackLine]`: main hand, off hand, ranged weapon and an
  unarmed strike (empty for creatures without `pc`).
"""

from typing import Literal

from aidm.data.character_data import CharacterRegistries
from aidm.data.registry import Registry
from aidm.data.srd_characters import SrdProficiency
from aidm.data.srd_equipment import SrdEquipment
from aidm.models.abilities import Ability
from aidm.models.character import PcData
from aidm.models.damage import DamageType
from aidm.models.features import AttackContext
from aidm.models.sheet import AttackLine
from aidm.models.state import Creature
from aidm.rules.abilities import ability_modifier
from aidm.rules.features import attack_bonus_mods, damage_bonus_mods, offhand_adds_ability

UNARMED_STRIKE_DAMAGE = 1
_RANGED = "Ranged"
_CATEGORY_PROFICIENCY = {"Simple": "simple-weapons", "Martial": "martial-weapons"}

type Hand = Literal["main_hand", "off_hand", "ranged"]


def _has(weapon: SrdEquipment, prop: str) -> bool:
    return any(p.index == prop for p in weapon.properties)


def weapon_proficient(
    pc: PcData, weapon: SrdEquipment, proficiencies: Registry[SrdProficiency]
) -> bool:
    category = _CATEGORY_PROFICIENCY.get(weapon.weapon_category or "")
    if category is not None and category in pc.weapon_proficiencies:
        return True
    entries = [proficiencies.find(index) for index in pc.weapon_proficiencies]
    return any(
        e is not None and e.reference is not None and e.reference.index == weapon.index
        for e in entries
    )


def weapon_attack_ability(creature: Creature, weapon: SrdEquipment) -> Ability:
    strength, dex = creature.abilities[Ability.STR], creature.abilities[Ability.DEX]
    if _has(weapon, "finesse"):
        return Ability.DEX if dex > strength else Ability.STR
    return Ability.DEX if weapon.weapon_range == _RANGED else Ability.STR


def wields_two_handed(pc: PcData, weapon: SrdEquipment) -> bool:
    if _has(weapon, "two-handed"):
        return True
    free = pc.equipped.shield is None and pc.equipped.off_hand is None
    return _has(weapon, "versatile") and free and weapon.two_handed_damage is not None


def attack_context(pc: PcData, weapon: SrdEquipment, hand: Hand) -> AttackContext:
    ranged = weapon.weapon_range == _RANGED
    return AttackContext(
        ranged=ranged,
        finesse=_has(weapon, "finesse"),
        two_handed=not ranged and wields_two_handed(pc, weapon),
        offhand=hand == "off_hand",
        other_hand_weapon=hand == "main_hand" and pc.equipped.off_hand is not None,
    )


def _with_mod(dice: str, mod: int) -> str:
    if mod > 0:
        return f"{dice}+{mod}"
    return f"{dice}-{-mod}" if mod < 0 else dice


def weapon_attack_line(
    creature: Creature, weapon: SrdEquipment, hand: Hand, regs: CharacterRegistries
) -> AttackLine:
    pc = creature.pc
    if pc is None or weapon.damage is None:
        raise ValueError(f"{weapon.index!r} is not a weapon wielded by a PC")
    ctx = attack_context(pc, weapon, hand)
    ability = weapon_attack_ability(creature, weapon)
    mod = ability_modifier(creature.abilities[ability])
    prof = creature.proficiency_bonus if weapon_proficient(pc, weapon, regs.proficiencies) else 0
    damage = weapon.damage
    if ctx.two_handed and weapon.two_handed_damage is not None:
        damage = weapon.two_handed_damage
    damage_mod = mod
    if ctx.offhand and mod > 0 and not offhand_adds_ability(creature, regs.features, ctx):
        damage_mod = 0
    damage_mod += damage_bonus_mods(creature, regs.features, ctx)
    reach = weapon.range
    return AttackLine(
        name=weapon.name,
        item=weapon.index,
        hand=hand,
        ability=ability,
        attack_bonus=mod + prof + attack_bonus_mods(creature, regs.features, ctx),
        damage=_with_mod(damage.damage_dice, damage_mod),
        damage_type=DamageType(damage.damage_type.index),
        range_band="ranged" if ctx.ranged else "melee",
        range_normal=reach.normal if reach else None,
        range_long=reach.long if reach else None,
    )


def _unarmed(creature: Creature) -> AttackLine:
    mod = ability_modifier(creature.abilities[Ability.STR])
    total = max(0, UNARMED_STRIKE_DAMAGE + mod)
    return AttackLine(
        name="Unarmed Strike",
        item=None,
        hand="unarmed",
        ability=Ability.STR,
        attack_bonus=mod + creature.proficiency_bonus,
        damage=str(total),
        damage_type=DamageType.BLUDGEONING,
        range_band="melee",
        range_normal=5,
    )


def attack_lines(creature: Creature, regs: CharacterRegistries) -> list[AttackLine]:
    pc = creature.pc
    if pc is None:
        return []
    lines: list[AttackLine] = []
    slots: tuple[tuple[Hand, str | None], ...] = (
        ("main_hand", pc.equipped.main_hand),
        ("off_hand", pc.equipped.off_hand),
        ("ranged", pc.equipped.ranged),
    )
    for hand, index in slots:
        weapon = regs.equipment.find(index) if index else None
        if weapon is not None and weapon.damage is not None:
            lines.append(weapon_attack_line(creature, weapon, hand, regs))
    return [*lines, _unarmed(creature)]
