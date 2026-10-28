"""Buying and selling on the menu while a shop is open here (M36.3, SPEC 6.2). Pure.

A shop trades while it is open (`world.shop_npc_id`, set by the shop visit) and its keeper stands
here, not hostile (`rules.shop`):
- `buy:<item>`: each item on the keeper's shelves (`rules.shop.npc_shop_stock`, the same stock the
  shop panel shows), `qty_max` the most the hero's gold buys (at least 1: the rules answer a
  purse too light plainly), at most the shop's lot limit. M44.3b (round 9 BB3): a ware the hero
  cannot pay for is an ordinary buy entry with no note (a "not enough gold" note read as not for
  sale, so the line went to the storyteller); the shop's rules refuse it with "No sale" and
  the reason, and a stunt naming it stays `other`;
- `sell:<item>`: each carried item with a market value, `qty_max` the units not in use (one in
  use says "unequip it first"). M36.8c: an item a trader pays nothing for is not listed, as the
  shop panel lists no Sell button for it (the menu matches the buttons; it also keeps the
  CHOOSE prompt in its budget).
The shop data is passed in (`TradeData`), never loaded here.

Public API: `TradeData(catalogue, shops)`, `trade_entries(view, trade) -> list[MenuEntry]`.
"""

from dataclasses import dataclass

from aidm.data.item_catalogue import CatalogueItem
from aidm.data.registry import Registry
from aidm.data.shop_defs import ShopTable
from aidm.models.action_menu import ActionKind, MenuEntry
from aidm.models.world import WorldNpc
from aidm.rules.menu_scene_view import SceneMenuView
from aidm.rules.shop import ShopRefused, StockEntry, buy_price, npc_shop_stock, sell_price
from aidm.rules.social import npc_is_hostile


@dataclass(frozen=True)
class TradeData:
    catalogue: Registry[CatalogueItem]
    shops: ShopTable


def _open_keeper(view: SceneMenuView) -> WorldNpc | None:
    world = view.state.world
    npc = world.npcs.get(world.shop_npc_id or "")
    if npc is None or npc.id not in view.people or npc_is_hostile(npc):
        return None
    return npc


def _affordable(value_gp: float, gold: int, shops: ShopTable) -> int:
    best = 0
    for qty in range(1, shops.max_qty + 1):
        if buy_price(value_gp, qty, shops) > gold:
            break
        best = qty
    return best


def _buy(view: SceneMenuView, trade: TradeData, stock: StockEntry, keeper: WorldNpc) -> MenuEntry:
    item = trade.catalogue.find(stock.item)
    name = item.name if item is not None else stock.item.replace("-", " ")
    price = stock.bulk or f"{stock.price_gp} gp each"
    can = _affordable(item.value_gp, view.gold, trade.shops) if item is not None else 0
    return MenuEntry(
        id=f"buy:{stock.item}",
        kind=ActionKind.BUY,
        label=f"Buy {name} from {keeper.name} ({price})",
        qty_max=max(1, can),
        item=stock.item,
    )


def _in_use(view: SceneMenuView, item: str) -> int:
    pc = view.state.creatures[view.actor_id].pc
    if pc is None:
        return 0
    gear = pc.equipped
    held = (gear.armor, gear.shield, gear.main_hand, gear.off_hand, gear.ranged)
    return sum(1 for slot in held if slot == item)


def _sells(view: SceneMenuView, trade: TradeData, keeper: WorldNpc) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    for row in view.sheet.inventory:
        item = trade.catalogue.find(row.item)
        if item is None or row.qty < 1:
            continue
        free = row.qty - _in_use(view, row.item)
        each = sell_price(item.value_gp, 1, trade.shops)
        if each < 1:
            continue
        note = "unequip it first" if free < 1 else ""
        out.append(
            MenuEntry(
                id=f"sell:{row.item}",
                kind=ActionKind.SELL,
                label=f"Sell {row.name} to {keeper.name} ({each} gp each, you carry {row.qty})",
                qty_max=max(1, min(free, trade.shops.max_qty)),
                note=note,
                item=row.item,
            )
        )
    return out


def trade_entries(view: SceneMenuView, trade: TradeData) -> list[MenuEntry]:
    keeper = _open_keeper(view)
    if keeper is None:
        return []
    try:
        stock = npc_shop_stock(view.state, keeper.id, trade.catalogue, trade.shops)
    except ShopRefused:
        return []
    buys = [_buy(view, trade, s, keeper) for s in stock]
    return [*buys, *_sells(view, trade, keeper)]
