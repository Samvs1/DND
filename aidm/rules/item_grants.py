"""Putting items into the party's hands, as events (shops, loot, quest rewards, grant_item).

ONE rule for every source: a catalogue item with a camp `supply` value feeds the party's long-rest
pool (`CampSuppliesChanged`), anything else (including plot items, which are not in the
catalogue) goes into the PC's inventory (`InventoryChanged`). Several grants in one call are
grouped so a stack that is granted twice in the same unapplied batch gets the right total.

Public API:
- `carried_qty(creature, item) -> int`: how many of `item` the PC carries.
- `key_fits(catalogue, item, feature) -> bool`: a key item whose `opens` lists the kind the
  feature's lock opens to (`LockInfo.opens`, M27.4; the feature's own kind without a lock).
- `party_key_for(state, feature, catalogue) -> str | None`: the first key a living PC carries that
  fits the feature (keys are generic items bound to feature kinds).
- `gain_item_events(state, grants, catalogue, extra_supplies=0) -> list[AnyEvent]`: `grants` are
  `(creature_id, item, qty)` triples; `extra_supplies` joins the pool in the same event.
"""

from collections.abc import Sequence

from aidm.data.item_catalogue import CatalogueItem
from aidm.data.registry import Registry
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.state import Creature, GameState
from aidm.models.world import WorldFeature
from aidm.rules.rests import adjust_camp_supplies


def carried_qty(creature: Creature, item: str) -> int:
    pc = creature.pc
    return 0 if pc is None else sum(row.qty for row in pc.inventory if row.item == item)


def gain_item_events(
    state: GameState,
    grants: Sequence[tuple[str, str, int]],
    catalogue: Registry[CatalogueItem],
    extra_supplies: int = 0,
) -> list[AnyEvent]:
    supplies = extra_supplies
    totals: dict[tuple[str, str], int] = {}
    for creature_id, item, qty in grants:
        entry = catalogue.find(item)
        if entry is not None and entry.supply > 0:
            supplies += entry.supply * qty
        else:
            totals[(creature_id, item)] = totals.get((creature_id, item), 0) + qty
    events: list[AnyEvent] = []
    for (creature_id, item), qty in totals.items():
        held = carried_qty(state.creatures[creature_id], item)
        events.append(
            InventoryChanged(creature_id=creature_id, item=item, delta=qty, qty=held + qty)
        )
    if supplies:
        events.extend(adjust_camp_supplies(state, supplies))
    return events


def key_fits(catalogue: Registry[CatalogueItem], item: str, feature: WorldFeature) -> bool:
    entry = catalogue.find(item)
    kind = feature.lock.opens if feature.lock is not None else feature.kind
    return entry is not None and kind.value in entry.opens


def party_key_for(
    state: GameState, feature: WorldFeature, catalogue: Registry[CatalogueItem]
) -> str | None:
    for creature in sorted(state.creatures.values(), key=lambda c: c.id):
        if creature.pc is None or creature.dead:
            continue
        for row in creature.pc.inventory:
            if key_fits(catalogue, row.item, feature):
                return row.item
    return None
