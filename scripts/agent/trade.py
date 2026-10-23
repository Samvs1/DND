"""The `trade` command's helpers (M29.4): open the place's shop through the table vote, read the
`shop_stock` it broadcasts, match what the tester typed to a stock line or a pack item.

`trade list` | `trade buy <item> [qty]` | `trade sell <item> [qty]`; the messages are the same
`shop_buy` / `shop_sell` the phone's Trade panel sends.

Public API: `parse_trade`, `shopkeeper_of`, `open_stock`, `match_line`, `stock_text`.
"""

from typing import Any

from scripts.agent.commands import UsageError
from scripts.agent.link import Link, open_link
from scripts.agent.session import Session

Msg = dict[str, Any]
USAGE = "trade list | trade buy <item> [qty] | trade sell <item> [qty]"


def parse_trade(words: list[str]) -> tuple[str, str, int]:
    """(verb, item words, quantity); a trailing number is the quantity."""
    if not words or words[0].lower() not in ("list", "buy", "sell"):
        raise UsageError(USAGE)
    verb, rest = words[0].lower(), list(words[1:])
    qty = 1
    if len(rest) > 1 and rest[-1].isdigit():
        qty = max(1, min(99, int(rest.pop())))
    if verb != "list" and not rest:
        raise UsageError(USAGE)
    return verb, " ".join(rest), qty


def shopkeeper_of(state: Msg) -> Msg:
    """The shopkeeper of the party's place (the open shop's, else the first one here)."""
    scene = state.get("scene") or {}
    npcs = {n["id"]: n for n in scene.get("npcs", [])}
    wanted = scene.get("shop_npc_id") or next(iter(scene.get("shopkeepers", [])), None)
    if wanted is None or wanted not in npcs:
        raise UsageError("there is no shopkeeper here: travel to a place with a shop")
    return npcs[wanted]


async def open_stock(session: Session, link: Link, keeper: Msg) -> Msg | None:
    """Propose the shop vote, let the other heroes accept, return the `shop_stock` message."""
    mark = link.conn.mark()
    await link.send({"type": "submit_action", "text": f"trade with {keeper['name']}"})
    for other in session.players:
        if other["token"] == link.conn.token:
            continue
        peer = await open_link(session, other)
        try:
            vote = peer.state.get("vote")
            if vote:
                await peer.send({"type": "vote", "vote_id": vote["vote_id"], "ready": True})
        finally:
            await peer.close()
    stocks = link.conn.of_type("shop_stock", mark)
    return stocks[-1] if stocks else None


def match_line(lines: list[Msg], text: str, id_key: str, name_key: str) -> Msg:
    """The one line whose id or name is `text` (exact), else the one containing it."""
    low = text.lower().replace(" ", "-")
    exact = [x for x in lines if low in (str(x[id_key]).lower(), str(x[name_key]).lower())]
    near = [
        x for x in lines if low in str(x[id_key]).lower() or text.lower() in x[name_key].lower()
    ]
    found = exact or near
    if len(found) != 1:
        names = ", ".join(str(x[id_key]) for x in (found or lines)[:12])
        raise UsageError(f"{text!r} matches {len(found)} items: {names}")
    return found[0]


def stock_text(stock: Msg, gold: int | None) -> str:
    rows = [f"  {s['item_id']}: {s['name']} {s['price_gp']}gp" for s in stock["stock"]]
    head = f"Shop of {stock.get('npc_name') or stock['npc_id']} (you have {gold}gp):"
    return "\n".join([head, *rows, "trade buy <item> [qty] | trade sell <item> [qty]"])
