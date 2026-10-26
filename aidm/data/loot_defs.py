"""Loot tables: data/bg3/loot_tables.json (SPEC 9 loot/XP; the engine owns every number).

`tiers[<region tier>][<monster type>]` is a `LootTable`: `gold` (a dice expression, "0" for none),
`item_chance` (percent), `items` (weighted item ids of the catalogue), and a camp supply find
(`supply_chance` percent for `supply` supplies). The monster type is the SRD creature type
(`humanoid`, `beast`, ...); `default` covers every other type and `boss` the campaign bosses.

Public API: `LootEntry`, `LootTable`, `LootTables.table_for(region_tier, kind)`,
`load_loot_tables(path=None)`, `loot_tables()` (cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_LOOT = Path(__file__).resolve().parents[2] / "data" / "bg3" / "loot_tables.json"
REQUIRED_KINDS = frozenset({"default", "boss"})


class LootEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item: str = Field(min_length=1)
    weight: int = Field(ge=1)


class LootTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gold: str = "0"
    item_chance: int = Field(default=0, ge=0, le=100)
    items: tuple[LootEntry, ...] = ()
    supply_chance: int = Field(default=0, ge=0, le=100)
    supply: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _items_needed(self) -> LootTable:
        if self.item_chance > 0 and not self.items:
            raise ValueError("a table with an item chance needs items")
        return self


class LootTables(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = ""
    tiers: dict[str, dict[str, LootTable]]

    @model_validator(mode="after")
    def _shape(self) -> LootTables:
        if set(self.tiers) != {"1", "2", "3"}:
            raise ValueError("loot tables need region tiers 1, 2 and 3")
        if any(not set(kinds) >= REQUIRED_KINDS for kinds in self.tiers.values()):
            raise ValueError("every tier needs the kinds default and boss")
        return self

    def table_for(self, region_tier: int, kind: str) -> LootTable:
        kinds = self.tiers[str(max(1, min(3, region_tier)))]
        return kinds.get(kind, kinds["default"])


def load_loot_tables(path: Path | None = None) -> LootTables:
    target = path if path is not None else DEFAULT_LOOT
    return LootTables.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def loot_tables() -> LootTables:
    return load_loot_tables()
