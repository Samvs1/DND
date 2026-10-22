"""Item-use events (M27.3, docs/next/GOAL_ITEMS.md; part of the `WorldEvents` union).

Emitted by the item-use interpreter (`aidm.rules.item_use`) and the long rest
(`aidm.rules.rests`), applied by `aidm.session.item_apply`. Payloads are resolved; the reducer
only assigns. The effects of a use travel in the EXISTING events (`ZoneSurfaceAdded`,
`ConditionApplied`, `Stabilized`, `InventoryChanged`, `CampSuppliesChanged`, `CheckResolved`,
`EconomyChanged`...); these events add only what is new.

Public API:
- `ItemUsed(creature_id, item, use_id, target, node, spends_charge, charges_left, forage)`: the
  hero used the catalogue item `item` by the use `use_id`. With `spends_charge` the inventory
  entry's charges become `charges_left` (None = a fresh, full entry); with `forage` the place
  `node` joins `World.foraged` (its once-per-place supplies use is spent).
- `ItemUseRefused(creature_id, item, message)`: pure log event: the use was refused and nothing
  was consumed; `message` tells the model what to narrate instead (an attempt, never a result).
- `BoonGained(boon)`: the hero's `ActiveBoon` joins `World.boons` (replacing the same use's).
- `BoonEnded(creature_id, use_id, reason)`: that boon leaves `World.boons`.
- `PlaceAlerted(node)`: a noisy use, or arriving in a dark place with a lit light (M27.12),
  alerted the place; foes met there cannot be surprised by
  the party until it leaves (`World.alerted`, cleared on `PartyMoved`).
- `PlacesCharted(nodes)`: these places become known on the map without a visit (`World.charted`).
- `LightLit(creature_id, item, reach)` (M27.12): the hero carries a lit light (`World.lights`,
  replacing that hero's); it travels with them from place to place.
- `LightEnded(creature_id, reason)` (M27.12): that hero's light ends (the long rest, from
  `aidm.rules.rests`; a dead bearer's light when the party moves on, `aidm.rules.light`).
- `ItemEvents`: the union of these classes.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.world import ActiveBoon, LightReach


class _ItemEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ItemUsed(_ItemEvent):
    type: Literal["item_used"] = "item_used"
    creature_id: str = Field(min_length=1)
    item: str = Field(min_length=1)
    use_id: str = Field(min_length=1)
    target: str | None = None
    node: str | None = None
    spends_charge: bool = False
    charges_left: int | None = Field(default=None, ge=0)
    forage: bool = False


class ItemUseRefused(_ItemEvent):
    type: Literal["item_use_refused"] = "item_use_refused"
    creature_id: str = Field(min_length=1)
    item: str = Field(min_length=1)
    message: str = Field(min_length=1)


class BoonGained(_ItemEvent):
    type: Literal["boon_gained"] = "boon_gained"
    boon: ActiveBoon


class BoonEnded(_ItemEvent):
    type: Literal["boon_ended"] = "boon_ended"
    creature_id: str = Field(min_length=1)
    use_id: str = Field(min_length=1)
    reason: str = ""


class PlaceAlerted(_ItemEvent):
    type: Literal["place_alerted"] = "place_alerted"
    node: str = Field(min_length=1)


class PlacesCharted(_ItemEvent):
    type: Literal["places_charted"] = "places_charted"
    nodes: tuple[str, ...] = Field(min_length=1)


class LightLit(_ItemEvent):
    type: Literal["light_lit"] = "light_lit"
    creature_id: str = Field(min_length=1)
    item: str = Field(min_length=1)
    reach: LightReach = "touching"


class LightEnded(_ItemEvent):
    type: Literal["light_ended"] = "light_ended"
    creature_id: str = Field(min_length=1)
    reason: str = ""


ItemEvents = (
    ItemUsed
    | ItemUseRefused
    | BoonGained
    | BoonEnded
    | PlaceAlerted
    | PlacesCharted
    | LightLit
    | LightEnded
)
