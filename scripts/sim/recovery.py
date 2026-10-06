"""Keeping the party alive between fights like a careful table would.

Short rests while any are left, then a long rest paid with camp supplies; supplies are bought
at the hub shop (a ready vote, then `shop_buy` by each hero with its own gold). Everything goes
through the protocol; a refused step is only logged (the party may press on hurt).

Public API: `recover`, `hp_ratio`.
"""

from typing import TYPE_CHECKING

from aidm.rules.rests import CAMP_SUPPLY_PER_MEMBER, MAX_SHORT_RESTS
from scripts.sim.bot import Bot
from scripts.sim.client import Msg

if TYPE_CHECKING:
    from scripts.sim.flow import Director

HURT = 0.8
BADLY_HURT = 0.6


def hp_ratio(d: "Director") -> float:
    heroes = [c for c in d.srv.table.state.creatures.values() if c.pc is not None]
    return min((c.hp / c.max_hp for c in heroes), default=1.0)


async def _buy_supplies(d: "Director", needed: int) -> None:
    host = d.proposer(d.party.fighter)
    mark = host.conn.mark()
    if not await d.propose(host, "I browse the wares"):
        return
    stock = next((m for m in host.conn.log[mark:] if m["type"] == "shop_stock"), None)
    if stock is None:
        d.report.say("no shop_stock after the shop vote")
        return
    for bot in d.party.bots:
        me = bot.me() or {}
        gold = me.get("gold") or 0
        item = next((s for s in stock["stock"] if s["item_id"] == "camp-meal-basket"), None)
        if item is None or gold < item["price_gp"] or needed <= 0:
            continue
        qty = min(gold // item["price_gp"], max(1, needed // max(1, item["supply"])))
        await _buy(bot, stock, item["item_id"], qty)
        needed -= qty * item["supply"]
        await d.settle()


async def _buy(bot: Bot, stock: Msg, item_id: str, qty: int) -> None:
    conn = bot.conn
    mark = conn.mark()
    await conn.send({"type": "shop_buy", "npc_id": stock["npc_id"], "item_id": item_id, "qty": qty})
    await conn.wait_for(lambda m: m["type"] in ("error", "notice", "snapshot"), 15.0, mark)


async def recover(d: "Director") -> None:
    state = d.srv.table.state
    if hp_ratio(d) < HURT and state.short_rests_used < MAX_SHORT_RESTS:
        await d.short_rest()
    if hp_ratio(d) >= BADLY_HURT:
        return
    cost = len([c for c in state.creatures.values() if c.pc is not None]) * CAMP_SUPPLY_PER_MEMBER
    if state.camp_supplies < cost and d.at_hub():
        await _buy_supplies(d, cost - state.camp_supplies)
    if state.camp_supplies >= cost:
        d.step("long rest")
        if not await d.propose(d.proposer(d.party.fighter), "We make camp for the night"):
            d.report.fail("the long rest vote did not pass")
    else:
        d.report.notes.append(f"party pressed on hurt ({hp_ratio(d):.2f}), no supplies for a rest")
