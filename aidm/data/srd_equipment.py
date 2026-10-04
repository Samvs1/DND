"""Typed SRD equipment entries (data/srd/equipment.json, 5e-bits 2014 format)."""

from __future__ import annotations

from aidm.data.srd_common import ApiRef, Cost, SrdModel


class WeaponDamage(SrdModel):
    damage_dice: str
    damage_type: ApiRef


class WeaponRange(SrdModel):
    normal: int
    long: int | None = None


class ArmorClass(SrdModel):
    base: int
    dex_bonus: bool
    max_bonus: int | None = None


class SrdEquipment(SrdModel):
    index: str
    name: str
    equipment_category: ApiRef
    weapon_category: str | None = None
    weapon_range: str | None = None
    category_range: str | None = None
    damage: WeaponDamage | None = None
    two_handed_damage: WeaponDamage | None = None
    range: WeaponRange | None = None
    throw_range: WeaponRange | None = None
    properties: list[ApiRef] = []
    armor_category: str | None = None
    armor_class: ArmorClass | None = None
    str_minimum: int = 0
    stealth_disadvantage: bool = False
    cost: Cost | None = None
    weight: float | None = None
    gear_category: ApiRef | None = None
    desc: list[str] = []
