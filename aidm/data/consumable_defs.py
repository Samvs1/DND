"""Consumable item schema and the data/bg3/consumables.json loader (potions and camp supplies).

Using a consumable is resolved by ONE generic path (`aidm.rules.items.use_item_events`); an item's
effect is data here, never an `if` on its id.

- `ConsumableDef(index, name, source, category, weight, heal, supply, value_gp)`: `index` is the
  inventory item id (the SRD magic item index for SRD potions); `category` is "potion" or
  "supply"; `heal` is the dice expression it restores ("2d4+2"); `supply` is the camp supply value
  of a food item (it goes to the party pool, never to an inventory); `value_gp` is its price in
  gold (rarity-based, docs/RULES_DECISIONS.md M4.2; grant caps and shops use it).
  BG3 (SPEC 7.2): drinking one, or giving one to an ally in the same zone, is a bonus action.

Public API: `load_consumable_defs(path=None) -> Registry[ConsumableDef]`, `consumable_defs()`
(default file, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.data.registry import Registry

DEFAULT_CONSUMABLES = Path(__file__).resolve().parents[2] / "data" / "bg3" / "consumables.json"


class ConsumableDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    category: Literal["potion", "supply"] = "potion"
    weight: float = Field(default=0.5, ge=0)
    heal: str | None = None
    supply: int = Field(default=0, ge=0)
    value_gp: float | None = Field(default=None, ge=0)


def load_consumable_defs(path: Path | None = None) -> Registry[ConsumableDef]:
    target = path if path is not None else DEFAULT_CONSUMABLES
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Registry(ConsumableDef.model_validate(item) for item in raw)


@functools.cache
def consumable_defs() -> Registry[ConsumableDef]:
    return load_consumable_defs()
