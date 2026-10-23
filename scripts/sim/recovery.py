"""Keeping the party alive between fights like a careful table would.

Short rests while any are left, then a long rest paid with camp supplies. The party starts with
the campaign's camp supplies (one long rest, M9.2); more are bought at the hub shop only when
short (a ready vote, then `shop_buy` by each hero with its own gold). Before the region boss a
careful table makes camp once (`camp`). Everything goes through the protocol; a refused step is
only logged (the party may press on hurt).

Public API: `recover`, `camp`, `hp_ratio`.
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
    # M29.2: the dead do not count (no rest heals them; the Scribe rewrites them).
    heroes = [c for c in d.srv.table.state.creatures.values() if c.pc is not None and not c.dead]
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
    # M29.2: the best camp food on sale (a smith only keeps rations), not only meal baskets.
    food = [s for s in stock["stock"] if s.get("category") == "supply" and s.get("supply")]
    item = max(food, key=lambda s: (s["supply"] / max(1, s["price_gp"]), s["supply"]), default=None)
    for bot in d.party.bots:
        me = bot.me() or {}
        gold = me.get("gold") or 0
        if item is None or gold < item["price_gp"] or needed <= 0:
            continue
        qty = min(gold // item["price_gp"], max(1, -(-needed // max(1, item["supply"]))), 10)
        await _buy(bot, stock, item["item_id"], qty)
        needed -= qty * item["supply"]
        await d.settle()


async def _buy(bot: Bot, stock: Msg, item_id: str, qty: int) -> None:
    conn = bot.conn
    mark = conn.mark()
    await conn.send({"type": "shop_buy", "npc_id": stock["npc_id"], "item_id": item_id, "qty": qty})
    await conn.wait_for(lambda m: m["type"] in ("error", "notice", "snapshot"), 15.0, mark)


def _cost(d: "Director") -> int:
    state = d.srv.table.state
    living = [c for c in state.creatures.values() if c.pc is not None and not c.dead]
    return len(living) * CAMP_SUPPLY_PER_MEMBER


async def camp(d: "Director") -> bool:
    """Make camp for the night (buying supplies at the hub first if short); True if rested."""
    state = d.srv.table.state
    cost = _cost(d)
    if state.camp_supplies < cost and d.at_hub():
        await _buy_supplies(d, cost - state.camp_supplies)
    if state.camp_supplies < cost:
        d.report.notes.append(f"no supplies for a long rest ({state.camp_supplies} < {cost})")
        return False
    d.step("long rest")
    before = state.camp_supplies
    if not await d.propose(d.proposer(d.party.fighter), "We make camp for the night"):
        d.report.fail("the long rest vote did not pass")
        return False
    if d.srv.table.state.camp_supplies != before - cost:
        d.report.fail(f"the long rest did not pay {cost} supplies (had {before})")
        return False
    d.long_rests += 1
    return True


async def recover(d: "Director", hurt: float = HURT, badly: float = BADLY_HURT) -> None:
    """Short rest below `hurt`, camp below `badly` (M29.2: a play style sets both)."""
    state = d.srv.table.state
    if hp_ratio(d) < hurt and state.short_rests_used < MAX_SHORT_RESTS:
        await d.short_rest()
    if hp_ratio(d) >= badly:
        return
    if not await camp(d):
        d.report.notes.append(f"party pressed on hurt ({hp_ratio(d):.2f})")
