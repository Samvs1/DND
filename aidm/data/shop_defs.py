"""Shop data: data/bg3/shops.json (SPEC 7.4: shop prices from data).

- `buy_markup`: the party pays `value_gp x buy_markup` (rounded up, at least 1 gp).
- `sell_fraction`: a shop pays `value_gp x sell_fraction` (half, 5e and BG3), rounded down.
- `max_qty`: the most one purchase or sale may cover.
- `kinds`: shop kinds. `keywords` match an NPC's role text, `categories` are the item categories
  the kind stocks, `always` are item ids it always has, `size` the number of stocked items.

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
    size: int = Field(ge=1, le=40)


class ShopTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = ""
    buy_markup: float = Field(gt=0)
    sell_fraction: float = Field(gt=0, le=1)
    max_qty: int = Field(ge=1)
    default_kind: str
    kinds: dict[str, ShopKind]

    @model_validator(mode="after")
    def _default_exists(self) -> ShopTable:
        if self.default_kind not in self.kinds:
            raise ValueError(f"default_kind {self.default_kind!r} is not a shop kind")
        return self


def load_shop_table(path: Path | None = None) -> ShopTable:
    target = path if path is not None else DEFAULT_SHOPS
    return ShopTable.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def shop_table() -> ShopTable:
    return load_shop_table()
