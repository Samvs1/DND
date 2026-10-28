"""The shop trade event (M5.6; its own module since M44.4 so `Memory.untold` can hold it).

Public API: `ItemsTraded(npc_id, creature_id, item, qty, gold, sold)`: log event of a shop sale or
purchase (gold and inventory move through `GoldChanged` / `InventoryChanged`). Part of
`aidm.models.world_events.WorldEvents`. THE reducer keeps it in `Memory.untold` until the next
`NarrationRecorded` (M44.4, round 9 BB9: a buy at the shop panel has no telling of its own, so
the next storyteller is told it).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ItemsTraded(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["items_traded"] = "items_traded"
    npc_id: str
    creature_id: str
    item: str = Field(min_length=1)
    qty: int = Field(ge=1)
    gold: int = Field(ge=0)
    sold: bool = False
