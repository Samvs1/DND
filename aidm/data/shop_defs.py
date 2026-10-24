"""Shop data: data/bg3/shops.json (SPEC 7.4: shop prices from data).

- `buy_markup`: the party pays `value_gp x buy_markup` (rounded up, at least 1 gp).
- `sell_fraction`: a shop pays `value_gp x sell_fraction` (half, 5e and BG3), rounded down.
- `max_qty`: the most one purchase or sale may cover.
- `kinds`: shop kinds. `keywords` match an NPC's role text, `categories` are the item categories
  the kind stocks, `always` are item ids it always has, `size` the number of stocked items;
  `one_of_each` (M29.6b) are categories it always has at least one item of (a general store's
  weapon and armour), picked like the rest of its shelf.
- `premium` (M31.2c): region tier -> number of shelf slots reserved for the dearest goods (items
  above the tier 1 price band, at most the region's tier) of the kind's categories plus
  `premium_categories`; a tier with no entry reserves none (tier 1 shelves are unchanged).
- `basics` (M29.6b): the categories every region's trader must sell (`stocks_basics`); a region
  whose cast has no trader of such a kind gets a peddler (`aidm.dm.campaign_shops`).

Public API: `ShopKind`, `ShopTable`, `load_shop_table(path=None)`, `shop_table()` (cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.data.item_catalogue import ItemCategory

DEFAULT_SHOPS = Path(__file__).resolve().parents[2] / "data" / "bg3" / "shops.json"


class ShopKind(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    keywords: tuple[str, ...] = ()
    categories: tuple[ItemCategory, ...] = Field(min_length=1)
    always: tuple[str, ...] = ()
    one_of_each: tuple[ItemCategory, ...] = ()
    size: int = Field(ge=1, le=40)
    premium: dict[int, int] = Field(default_factory=dict)
    premium_categories: tuple[ItemCategory, ...] = ()

    def premium_picks(self, region_tier: int) -> int:
        return self.premium.get(region_tier, 0)

    def sells(self, category: ItemCategory) -> bool:
        return category in self.categories or category in self.one_of_each


class ShopTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = ""
    buy_markup: float = Field(gt=0)
    sell_fraction: float = Field(gt=0, le=1)
    max_qty: int = Field(ge=1)
    default_kind: str
    kinds: dict[str, ShopKind]
    basics: tuple[ItemCategory, ...] = ()

    def stocks_basics(self, kind: str) -> bool:
        shape = self.kinds[kind]
        return all(shape.sells(c) for c in self.basics)

    @model_validator(mode="after")
    def _default_exists(self) -> ShopTable:
        if self.default_kind not in self.kinds:
            raise ValueError(f"default_kind {self.default_kind!r} is not a shop kind")
        if not self.stocks_basics(self.default_kind):
            raise ValueError("the default shop kind must sell every basic category")
        return self


def load_shop_table(path: Path | None = None) -> ShopTable:
    target = path if path is not None else DEFAULT_SHOPS
    return ShopTable.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def shop_table() -> ShopTable:
    return load_shop_table()
