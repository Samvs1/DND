"""The item catalogue: ONE view of every item usable in play (SPEC 7.4 Items, >= 80 entries).

Sources (all data, no per-item code):
- SRD equipment (data/srd/equipment.json): weapons, armor, adventuring gear and tools. Mounts and
  vehicles are not items and are left out. Value = cost converted to gp.
- data/bg3/consumables.json: potions (healing tiers plus a few simple draughts) and camp
  supplies (`supply` > 0: food that feeds the party's long-rest pool).
- data/bg3/key_items.json: generic keys bound to feature kinds (`opens`).
- spell scrolls: one per shipped spell, inventory key `scroll-of-<spell index>` (DECISIONS M2.5),
  priced by spell level (`SCROLL_VALUE_GP`, house numbers, docs/RULES_DECISIONS.md M5.6).

`tier` is the lowest region tier a shop stocks the item at (`tier_for_value`: value <= 75 gp is 1,
<= 300 gp is 2, else 3: the `item_value_cap_gp` steps of data/bg3/dm_tiers.json).

Public API:
- `ItemCategory` (weapon, armor, gear, tool, potion, supply, key, scroll).
- `CatalogueItem(id, name, category, value_gp, weight, tier, supply, heal, opens)`;
  `.index` is `id`.
- `KeyDef`, `load_key_defs(path=None)`, `key_defs()`.
- `build_item_catalogue(equipment, consumables, keys, spell_levels, spell_names) -> Registry`.
- `item_catalogue() -> Registry[CatalogueItem]`: the default, cached.
- `tier_for_value(value_gp) -> int`.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from aidm.data.consumable_defs import ConsumableDef, consumable_defs
from aidm.data.registry import Registry
from aidm.data.spell_defs import spell_defs
from aidm.data.srd import srd
from aidm.data.srd_equipment import SrdEquipment

DEFAULT_KEYS = Path(__file__).resolve().parents[2] / "data" / "bg3" / "key_items.json"
GP_PER_UNIT = {"cp": 0.01, "sp": 0.1, "ep": 0.5, "gp": 1.0, "pp": 10.0}
SCROLL_PREFIX = "scroll-of-"
SCROLL_VALUE_GP = {0: 25.0, 1: 75.0, 2: 150.0, 3: 300.0}
MAX_SCROLL_VALUE_GP = 300.0
SKIPPED_SRD_CATEGORIES = frozenset({"mounts-and-vehicles"})
SRD_CATEGORY = {"weapon": "weapon", "armor": "armor", "tools": "tool"}


class ItemCategory(StrEnum):
    WEAPON = "weapon"
    ARMOR = "armor"
    GEAR = "gear"
    TOOL = "tool"
    POTION = "potion"
    SUPPLY = "supply"
    KEY = "key"
    SCROLL = "scroll"


class CatalogueItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: ItemCategory
    value_gp: float = Field(ge=0)
    weight: float = Field(default=0, ge=0)
    tier: int = Field(ge=1, le=3)
    supply: int = Field(default=0, ge=0)
    heal: str | None = None
    opens: tuple[str, ...] = ()

    @property
    def index(self) -> str:
        return self.id


class KeyDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    opens: tuple[str, ...] = Field(min_length=1)
    value_gp: float = Field(ge=0)
    weight: float = Field(default=0.1, ge=0)


def tier_for_value(value_gp: float) -> int:
    if value_gp <= 75:
        return 1
    return 2 if value_gp <= 300 else 3


def load_key_defs(path: Path | None = None) -> Registry[KeyDef]:
    raw = json.loads((path if path is not None else DEFAULT_KEYS).read_text(encoding="utf-8"))
    return Registry(KeyDef.model_validate(item) for item in raw)


@functools.cache
def key_defs() -> Registry[KeyDef]:
    return load_key_defs()


def _equipment_item(entry: SrdEquipment) -> CatalogueItem | None:
    category = entry.equipment_category.index
    cost = entry.cost
    if category in SKIPPED_SRD_CATEGORIES or cost is None or cost.unit not in GP_PER_UNIT:
        return None
    value = cost.quantity * GP_PER_UNIT[cost.unit]
    return CatalogueItem(
        id=entry.index,
        name=entry.name,
        category=ItemCategory(SRD_CATEGORY.get(category, "gear")),
        value_gp=value,
        weight=entry.weight or 0.0,
        tier=tier_for_value(value),
    )


def _consumable_item(entry: ConsumableDef) -> CatalogueItem:
    value = entry.value_gp or 0.0
    return CatalogueItem(
        id=entry.index,
        name=entry.name,
        category=ItemCategory(entry.category),
        value_gp=value,
        weight=entry.weight,
        tier=tier_for_value(value),
        supply=entry.supply,
        heal=entry.heal,
    )


def _key_item(entry: KeyDef) -> CatalogueItem:
    return CatalogueItem(
        id=entry.index,
        name=entry.name,
        category=ItemCategory.KEY,
        value_gp=entry.value_gp,
        weight=entry.weight,
        tier=tier_for_value(entry.value_gp),
        opens=entry.opens,
    )


def _scroll_item(spell: str, level: int, name: str) -> CatalogueItem:
    value = SCROLL_VALUE_GP.get(level, MAX_SCROLL_VALUE_GP)
    return CatalogueItem(
        id=f"{SCROLL_PREFIX}{spell}",
        name=f"Scroll of {name}",
        category=ItemCategory.SCROLL,
        value_gp=value,
        weight=0.0,
        tier=tier_for_value(value),
    )


def build_item_catalogue(
    equipment: Registry[SrdEquipment],
    consumables: Registry[ConsumableDef],
    keys: Registry[KeyDef],
    spell_levels: Mapping[str, int],
    spell_names: Mapping[str, str],
) -> Registry[CatalogueItem]:
    items = [_equipment_item(e) for e in equipment.all()]
    found = [i for i in items if i is not None]
    found += [_consumable_item(c) for c in consumables.all()]
    found += [_key_item(k) for k in keys.all()]
    for spell in sorted(spell_levels):
        found.append(_scroll_item(spell, spell_levels[spell], spell_names.get(spell, spell)))
    return Registry(found)


@functools.cache
def item_catalogue() -> Registry[CatalogueItem]:
    data = srd()
    spells = spell_defs()
    return build_item_catalogue(
        data.equipment,
        consumable_defs(),
        key_defs(),
        {s.index: s.level for s in spells.all()},
        {s.index: data.spells.get(s.index).name for s in spells.all() if s.index in data.spells},
    )
