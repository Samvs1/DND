"""Consumable item schema and the data/bg3/consumables.json loader (potions; M5.6 adds more).

Using a consumable is resolved by ONE generic path (`aidm.rules.items.use_item_events`); an item's
effect is data here, never an `if` on its id.

- `ConsumableDef(index, name, source, heal)`: `index` is the inventory item id (the SRD magic
  item index for potions); `heal` is the dice expression it restores ("2d4+2").
  BG3 (SPEC 7.2): drinking one, or giving one to an ally in the same zone, is a bonus action.

Public API: `load_consumable_defs(path=None) -> Registry[ConsumableDef]`, `consumable_defs()`
(default file, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from aidm.data.registry import Registry

DEFAULT_CONSUMABLES = Path(__file__).resolve().parents[2] / "data" / "bg3" / "consumables.json"


class ConsumableDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    heal: str | None = None


def load_consumable_defs(path: Path | None = None) -> Registry[ConsumableDef]:
    target = path if path is not None else DEFAULT_CONSUMABLES
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Registry(ConsumableDef.model_validate(item) for item in raw)


@functools.cache
def consumable_defs() -> Registry[ConsumableDef]:
    return load_consumable_defs()
