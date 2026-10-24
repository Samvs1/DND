"""Shops: stock, prices, buying and selling, pure (SPEC 7.4 Items, 9). Data: data/bg3/shops.json.

Stock is generated, not stored: it is a pure function of the campaign seed, the shopkeeper and the
region tier (`npc_shop_stock`), so replaying the log gives the same shelves. Quantities are
unlimited (a purchase is capped by `max_qty`), which keeps shop state out of the event log; only
gold, inventory and the camp supply pool move, through the usual events, plus a log-only
`ItemsTraded`. Camp supplies bought go to the party pool (`rules.item_grants`).

Prices: the party pays `value_gp x buy_markup` rounded up (at least 1 gp); a shop pays half the
value, rounded down (5e "Selling Treasure", BG3 vendors) and refuses worthless items. A shop only
trades while it is open (`ShopOpened` sets `world.shop_npc_id`) and its keeper is not hostile.

Public API:
- `ShopRefusal`, `ShopRefused(reason, detail)`: typed refusals; nothing is spent or consumed.
- `StockEntry(item, price_gp, unit_gp, bulk)`: `price_gp` buys one; `unit_gp` is the exact price of
  one before the whole-gold rounding (several cost `buy_price` of the lot: 10 rations at 0.5 gp
  cost 5 gp) and `bulk` says so for an item under 1 gp ("2 for 1 gp", M29.7d R6).
  `shop_kind(npc, table) -> str` (role keywords, else the default);
  `role_shop_kind(role, table) -> str` (the same from a role text).
- `buy_price(value_gp, qty, table)`, `sell_price(value_gp, qty, table)`;
  `bulk_note(unit_gp) -> str`: "<n> for <m> gp" for a price under 1 gp ("" otherwise).
- A sale that would fetch less than 1 gp is refused (`WORTHLESS`) with the true reason: a trader
  pays half an item's value in whole gold (M29.7d R6: never "not worth buying").
- `shop_stock(catalogue, table, kind, region_tier, rng) -> tuple[StockEntry, ...]`: the `always`
  items, one of each `one_of_each` category (M29.6b), then random picks up to `size`.
- `npc_shop_stock(state, npc_id, catalogue, table) -> tuple[StockEntry, ...]`.
- `buy_events(state, pc_id, npc_id, item, qty, catalogue, table) -> list[AnyEvent]`.
- `sell_events(state, pc_id, npc_id, item, qty, catalogue, table) -> list[AnyEvent]`.
"""

import math
import random
from dataclasses import dataclass
from enum import StrEnum

from aidm.data.item_catalogue import CatalogueItem
from aidm.data.registry import Registry
from aidm.data.shop_defs import ShopKind, ShopTable
from aidm.models.events import AnyEvent, GoldChanged, InventoryChanged
from aidm.models.state import Creature, GameState
from aidm.models.world import WorldNpc
from aidm.models.world_events import ItemsTraded
from aidm.rules.dice import Rng
from aidm.rules.item_grants import carried_qty, gain_item_events
from aidm.rules.social import npc_is_hostile


class ShopRefusal(StrEnum):
    CLOSED = "closed"
    BAD_QTY = "bad_qty"
    UNKNOWN_ITEM = "unknown_item"
    NOT_IN_STOCK = "not_in_stock"
    NOT_ENOUGH_GOLD = "not_enough_gold"
    NOT_CARRIED = "not_carried"
    EQUIPPED = "equipped"
    WORTHLESS = "worthless"
    NOT_TRADABLE = "not_tradable"


class ShopRefused(ValueError):
    """The trade is not possible; nothing was spent or consumed."""

    def __init__(self, reason: ShopRefusal, detail: str = "") -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class StockEntry:
    item: str
    price_gp: int
    unit_gp: float = 0.0
    bulk: str = ""


def shop_kind(npc: WorldNpc, table: ShopTable) -> str:
    return role_shop_kind(npc.role, table)


def role_shop_kind(role_text: str, table: ShopTable) -> str:
    role = role_text.lower()
    for name, kind in table.kinds.items():
        if any(word in role for word in kind.keywords):
            return name
    return table.default_kind


def buy_price(value_gp: float, qty: int, table: ShopTable) -> int:
    return max(1, math.ceil(value_gp * qty * table.buy_markup - 1e-9))


def sell_price(value_gp: float, qty: int, table: ShopTable) -> int:
    return math.floor(value_gp * qty * table.sell_fraction + 1e-9)


def bulk_note(unit_gp: float) -> str:
    if unit_gp <= 0 or abs(unit_gp - round(unit_gp)) < 1e-9:
        return ""  # a whole-gold price needs no lot note (M31.1e: 1.5 gp each is "2 for 3 gp")
    for qty in range(2, 101):
        total = unit_gp * qty
        if abs(total - round(total)) < 1e-9:
            return f"{qty} for {round(total)} gp"
    return ""


def _entry(item: CatalogueItem, table: ShopTable) -> StockEntry:
    unit = item.value_gp * table.buy_markup
    price = buy_price(item.value_gp, 1, table)
    return StockEntry(item=item.id, price_gp=price, unit_gp=unit, bulk=bulk_note(unit))


def _premium_picks(
    catalogue: Registry[CatalogueItem],
    shape: ShopKind,
    region_tier: int,
    rng: Rng,
    chosen: list[str],
) -> None:
    """M31.2c: a later-region shop keeps its best goods on the shelf (gold buys something)."""
    cats = (*shape.categories, *shape.premium_categories)
    best = sorted(
        i.id
        for i in catalogue.all()
        if i.category in cats
        and 2 <= i.tier <= region_tier
        and i.value_gp > 0
        and i.id not in chosen
    )
    for _ in range(min(shape.premium_picks(region_tier), len(best), shape.size - len(chosen))):
        chosen.append(best.pop(rng.randint(0, len(best) - 1)))


def shop_stock(
    catalogue: Registry[CatalogueItem],
    table: ShopTable,
    kind: str,
    region_tier: int,
    rng: Rng,
) -> tuple[StockEntry, ...]:
    shape = table.kinds[kind]
    chosen = [i for i in shape.always if i in catalogue]
    shelf = sorted(
        (
            item
            for item in catalogue.all()
            if shape.sells(item.category) and item.tier <= region_tier and item.value_gp > 0
        ),
        key=lambda item: item.id,
    )
    _premium_picks(catalogue, shape, region_tier, rng, chosen)
    for category in shape.one_of_each:  # M29.6b: a general store always has a weapon and armour
        some = [i.id for i in shelf if i.category == category and i.id not in chosen]
        if some:
            chosen.append(some[rng.randint(0, len(some) - 1)])
    pool = [i.id for i in shelf if i.category in shape.categories and i.id not in chosen]
    while pool and len(chosen) < shape.size:
        chosen.append(pool.pop(rng.randint(0, len(pool) - 1)))
    entries = [_entry(catalogue.get(i), table) for i in chosen]
    return tuple(sorted(entries, key=lambda e: (e.price_gp, e.item)))


def _keeper(state: GameState, npc_id: str) -> WorldNpc:
    npc = state.world.npcs.get(npc_id)
    if npc is None or state.world.shop_npc_id != npc_id or npc_is_hostile(npc):
        raise ShopRefused(ShopRefusal.CLOSED, "that shop is not open")
    return npc


def npc_shop_stock(
    state: GameState, npc_id: str, catalogue: Registry[CatalogueItem], table: ShopTable
) -> tuple[StockEntry, ...]:
    npc = state.world.npcs.get(npc_id)
    if npc is None or npc_is_hostile(npc):
        raise ShopRefused(ShopRefusal.CLOSED, "that shop is not open")
    rng = random.Random(f"{state.seed}:shop:{npc.id}")
    return shop_stock(catalogue, table, shop_kind(npc, table), state.world.region_tier, rng)


def _trader(state: GameState, pc_id: str, qty: int, table: ShopTable) -> Creature:
    pc = state.creatures.get(pc_id)
    if pc is None or pc.pc is None or pc.dead:
        raise ShopRefused(ShopRefusal.CLOSED, "only a living hero can trade")
    if not 1 <= qty <= table.max_qty:
        raise ShopRefused(ShopRefusal.BAD_QTY, f"trade 1 to {table.max_qty} at a time")
    return pc


def buy_events(
    state: GameState,
    pc_id: str,
    npc_id: str,
    item: str,
    qty: int,
    catalogue: Registry[CatalogueItem],
    table: ShopTable,
) -> list[AnyEvent]:
    pc = _trader(state, pc_id, qty, table)
    _keeper(state, npc_id)
    entry = catalogue.find(item)
    if entry is None:
        raise ShopRefused(ShopRefusal.UNKNOWN_ITEM, item)
    if item not in {s.item for s in npc_shop_stock(state, npc_id, catalogue, table)}:
        raise ShopRefused(ShopRefusal.NOT_IN_STOCK, entry.name)
    cost = buy_price(entry.value_gp, qty, table)
    gold = pc.pc.gold if pc.pc is not None else 0
    if gold < cost:
        raise ShopRefused(ShopRefusal.NOT_ENOUGH_GOLD, f"{cost} gp needed, {gold} gp carried")
    events: list[AnyEvent] = [GoldChanged(creature_id=pc_id, delta=-cost, gold=gold - cost)]
    events.extend(gain_item_events(state, [(pc_id, item, qty)], catalogue))
    events.append(ItemsTraded(npc_id=npc_id, creature_id=pc_id, item=item, qty=qty, gold=cost))
    return events


def _equipped_count(pc: Creature, item: str) -> int:
    gear = pc.pc.equipped if pc.pc is not None else None
    if gear is None:
        return 0
    held = (gear.armor, gear.shield, gear.main_hand, gear.off_hand, gear.ranged)
    return sum(1 for slot in held if slot == item)


def sell_events(
    state: GameState,
    pc_id: str,
    npc_id: str,
    item: str,
    qty: int,
    catalogue: Registry[CatalogueItem],
    table: ShopTable,
) -> list[AnyEvent]:
    pc = _trader(state, pc_id, qty, table)
    _keeper(state, npc_id)
    carried = carried_qty(pc, item)
    if carried < qty:
        raise ShopRefused(ShopRefusal.NOT_CARRIED, f"carrying {carried}, selling {qty}")
    entry = catalogue.find(item)
    if entry is None:
        raise ShopRefused(ShopRefusal.NOT_TRADABLE, "this has no market value")
    if carried - qty < _equipped_count(pc, item):
        raise ShopRefused(ShopRefusal.EQUIPPED, f"unequip {entry.name} first")
    gain = sell_price(entry.value_gp, qty, table)
    if gain < 1:
        worth = f"{entry.value_gp * qty:g} gp"
        raise ShopRefused(
            ShopRefusal.WORTHLESS,
            f"a trader pays half an item's value in whole gold, so {entry.name} (worth {worth})"
            " fetches nothing",
        )
    gold = pc.pc.gold if pc.pc is not None else 0
    return [
        InventoryChanged(creature_id=pc_id, item=item, delta=-qty, qty=carried - qty),
        GoldChanged(creature_id=pc_id, delta=gain, gold=gold + gain),
        ItemsTraded(npc_id=npc_id, creature_id=pc_id, item=item, qty=qty, gold=gain, sold=True),
    ]
