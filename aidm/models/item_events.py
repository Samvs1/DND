"""Item-use events (M27.3, docs/next/GOAL_ITEMS.md; part of the `WorldEvents` union).

Emitted by the item-use interpreter (`aidm.rules.item_use`) and the long rest
(`aidm.rules.rests`), applied by `aidm.session.item_apply`. Payloads are resolved; the reducer
only assigns. The effects of a use travel in the EXISTING events (`ZoneSurfaceAdded`,
`ConditionApplied`, `Stabilized`, `InventoryChanged`, `CampSuppliesChanged`, `CheckResolved`,
`EconomyChanged`...); these events add only what is new.

Public API:
- `ItemUsed(creature_id, item, use_id, target, node, spends_charge, charges_left, forage,
  no_effect)`: the
  hero used the catalogue item `item` by the use `use_id`. With `spends_charge` the inventory
  entry's charges become `charges_left` (None = a fresh, full entry); with `forage` the place
  `node` joins `World.foraged` (its once-per-place supplies use is spent). `no_effect` (M27.6):
  the use happened and changed nothing (holy water on a beast, a torch where nothing burns).
- `ItemUseRefused(creature_id, item, message)`: pure log event: the use was refused and nothing
  was consumed; `message` tells the model what to narrate instead (an attempt, never a result).
- `BoonGained(boon)`: the hero's `ActiveBoon` joins `World.boons` (replacing the same use's).
- `BoonEnded(creature_id, use_id, reason)`: that boon leaves `World.boons`.
- `PlaceAlerted(node, reason)`: a noisy use (`reason` "noise"), or a light lit in or carried
  into a dark place ("light", M27.5), alerted the place; foes met there cannot be surprised by
  the party until it leaves (`World.alerted` + `World.alerted_by`, cleared on `PartyMoved`).
- `PlacesCharted(nodes)`: these places become known on the map without a visit (`World.charted`).
- `LightLit(creature_id, item, reach)` (M27.12): the hero carries a lit light (`World.lights`,
  replacing that hero's); it travels with them from place to place.
- `LightEnded(creature_id, reason, item)` (M27.12): that hero's light ends (the long rest, from
  `aidm.rules.rests`; a dead bearer's light when the party moves on, `aidm.rules.light`; put
  out, reason "doused" with the light's `item`, M27.5 `aidm.rules.light.put_out`).
- `FeatureUnlocked(feature_id, creature_id, method, item)` (M27.4): the feature's lock is gone
  (`WorldFeature.lock` becomes None): opened with the party's fitting key, picked or forced
  (`aidm.rules.locks`); `item` is the key or the gear that did it, if any.
- `HandedOver(creature_id, to_id, item, keepsake_id, qty, gold)` (M29.7a R8): a hero handed
  something to another hero: `qty` of the inventory item `item` or `gold` coins (moved by the
  `InventoryChanged` / `GoldChanged` pair that comes with it; this event is their record), or
  the keepsake `keepsake_id` (moved by this event, `aidm.rules.hero_handing`).
- `ItemEvents`: the union of these classes.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.world import ActiveBoon, AlertCause, LightReach


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
    no_effect: bool = False  # M27.6: the use happened and changed nothing (data adds effects)


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
    reason: AlertCause = "noise"  # M27.5: old logs default to noise


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
    item: str | None = None  # M27.5: the light put out (a doused light names it)


class FeatureUnlocked(_ItemEvent):
    type: Literal["feature_unlocked"] = "feature_unlocked"
    feature_id: str = Field(min_length=1)
    creature_id: str = Field(min_length=1)
    method: Literal["key", "pick", "force"]
    item: str | None = None


class HandedOver(_ItemEvent):
    type: Literal["handed_over"] = "handed_over"
    creature_id: str = Field(min_length=1)
    to_id: str = Field(min_length=1)
    item: str | None = None
    keepsake_id: str | None = None
    qty: int = Field(default=0, ge=0)
    gold: int = Field(default=0, ge=0)


ItemEvents = (
    ItemUsed
    | ItemUseRefused
    | BoonGained
    | BoonEnded
    | PlaceAlerted
    | PlacesCharted
    | LightLit
    | LightEnded
    | FeatureUnlocked
    | HandedOver
)
