"""Typed SRD equipment entries (data/srd/equipment.json, 5e-bits 2014 format)."""

from __future__ import annotations

from aidm.data.srd_common import ApiRef, Cost, SrdModel


class WeaponDamage(SrdModel):
    damage_dice: str
    damage_type: ApiRef


class WeaponRange(SrdModel):
    normal: int
    long: int | None = None


class PackContent(SrdModel):
    """One entry of an equipment pack's contents (SRD 5.1 Equipment Packs)."""

    item: ApiRef
    quantity: int = 1


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
    contents: list[PackContent] = []  # M27.10: an equipment pack's items (SRD 5.1)


def pack_items(item: SrdEquipment | None) -> list[tuple[str, int]]:
    """(item index, quantity) of an equipment pack's SRD contents; empty for anything else.
    The one source for opening a pack, at creation (M27.10) and from an old save (M29.3b)."""
    return [(c.item.index, c.quantity) for c in item.contents] if item is not None else []
