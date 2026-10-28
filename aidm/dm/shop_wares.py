"""The open shop's real wares, for the storyteller and the closed world (M44.4, round 9 BB9).

Round 9 told rope, oiled hide and lamp oil at an open cart that sold none of them, priced a
"steel shirt" at eighty, and denied a stocked Scroll of Revivify (the guard did not know its
name). The stock is a pure function of the state (`rules.shop.npc_shop_stock`, the shelves the
menu and the shop panel show), so the one context builder lists it in the manifest and the
entity registry (`aidm.dm.entities`, the names the guard already reads) knows its names. Only
while the shop is open (`world.shop_npc_id`) and its keeper is here and not hostile; a shop
holds at most 14 wares (`data/bg3/shops.json`), so the line is not capped.

Public API: `open_wares(state) -> tuple[str, tuple[tuple[str, str], ...]] | None` (the keeper's
name and each ware's name and price), `ware_names(state) -> frozenset[str]`,
`wares_lines(state) -> list[str]`.
"""

from aidm.data.item_catalogue import item_catalogue
from aidm.data.shop_defs import shop_table
from aidm.models.state import GameState
from aidm.rules.scene import current_scene
from aidm.rules.shop import npc_shop_stock
from aidm.rules.social import npc_is_hostile

type Wares = tuple[str, tuple[tuple[str, str], ...]]


def open_wares(state: GameState) -> Wares | None:
    npc = state.world.npcs.get(state.world.shop_npc_id or "")
    if npc is None or npc_is_hostile(npc) or npc.id not in current_scene(state).npc_ids:
        return None
    catalogue = item_catalogue()
    wares: list[tuple[str, str]] = []
    for stock in npc_shop_stock(state, npc.id, catalogue, shop_table()):
        item = catalogue.find(stock.item)
        name = item.name if item is not None else stock.item.replace("-", " ")
        wares.append((name, stock.bulk or f"{stock.price_gp} gp"))
    return npc.name, tuple(wares)


def ware_names(state: GameState) -> frozenset[str]:
    shop = open_wares(state)
    return frozenset(name for name, _ in shop[1]) if shop is not None else frozenset()


def wares_lines(state: GameState) -> list[str]:
    shop = open_wares(state)
    if shop is None or not shop[1]:
        return []
    keeper, wares = shop
    told = "; ".join(f"{name} {price}" for name, price in wares)
    return [f"Wares of {keeper} (shop open; only these are for sale, at these prices): {told}"]
