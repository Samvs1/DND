"""The small table moves of the M29.2 campaign bots, all through the protocol.

- `shop`: at a hub. `basic` buys the healer's kit once (`scripts.sim.gear.stock_up`), `spender`
  also buys the best healing potions each hero can pay for, `none` (the hoarder) buys nothing
  (camp food is still bought by `scripts.sim.recovery.camp` when the party is out of it).
- `revive`: a dead hero is rewritten by the Scribe, paid by the richest living hero.
- `level_all`: every living hero takes every level-up it has earned.
- `search_here` / `pick_up_all`: one search of the place (the fake storyteller rolls Perception,
  `scripts.sim.fake_dm`), then every visible thing is picked up by typing it.
- `peace_item` / `give`: the hero who carries the region's Peace item hands it to the master.

Public API: `shop`, `revive`, `level_all`, `search_here`, `pick_up_all`, `peace_item`, `give`,
`living`, `spent`, `best_at(d, skill)` (who rolls a parley: the best Persuasion).
"""

from typing import TYPE_CHECKING

from aidm.models.quests import RouteKind
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.progression import region_of
from scripts.sim.bot import Bot
from scripts.sim.checks import hero_up
from scripts.sim.client import Msg
from scripts.sim.explore import scene_of
from scripts.sim.fake_dm import SEARCH_TEXT
from scripts.sim.gear import stock_up
from scripts.sim.levelup import level_up_bot
from scripts.sim.shapes import main_ability
from scripts.sim.spells import POTIONS
from scripts.sim.styles import Style

if TYPE_CHECKING:
    from scripts.sim.flow import Director

NO_LEVEL = "no level-up options offered"
MAX_LEVELS_AT_ONCE = 3
MAX_PICKUPS = 4
POTIONS_PER_HERO = 3
REPLY = ("error", "notice", "snapshot")


def living(d: "Director") -> list[Bot]:
    return [b for b in d.party.bots if hero_up(d.srv.table.state, b.hero_id)]


def spent(d: "Director") -> bool:
    """A living hero is hurt or has used a spell slot or feature use (a rest would help)."""
    pcs = [c for c in d.srv.table.state.creatures.values() if c.pc is not None and not c.dead]
    return any(
        c.hp < c.max_hp or any(r.current < r.maximum for r in c.resources.values()) for c in pcs
    )


async def _reply(bot: Bot, send: Msg, timeout: float = 15.0) -> Msg:
    mark = bot.conn.mark()
    await bot.conn.send(send)
    return await bot.conn.wait_for(lambda m: m["type"] in REPLY, timeout * bot.patience, mark)


async def _browse(d: "Director") -> Msg | None:
    host = d.proposer(d.party.fighter)
    mark = host.conn.mark()
    if not await d.propose(host, "I browse the wares"):
        return None
    return next((m for m in reversed(host.conn.log[mark:]) if m["type"] == "shop_stock"), None)


async def _potions(d: "Director") -> None:
    stock = await _browse(d)
    if stock is None:
        d.report.notes.append("no shop stock for the potions")
        return
    lines = {s["item_id"]: s for s in stock["stock"]}
    for bot in living(d):
        for potion in (p for p in POTIONS if p in lines):
            price = lines[potion]["price_gp"]
            qty = min(POTIONS_PER_HERO, ((bot.me() or {}).get("gold") or 0) // max(1, price))
            if qty > 0:
                send = {"type": "shop_buy", "npc_id": stock["npc_id"], "item_id": potion}
                await _reply(bot, {**send, "qty": qty})
                await d.settle()
                d.report.gear["potions_bought"] += qty
                break


async def shop(d: "Director", style: Style, first: bool) -> None:
    if style.shop == "none" or not d.at_hub():
        return
    if first:
        await stock_up(d)
    if style.shop == "spender":
        await _potions(d)


async def revive(d: "Director") -> None:
    game = d.srv.table.state
    for bot in d.party.bots:
        if not game.creatures[bot.hero_id].dead:
            continue
        payers = sorted(living(d), key=lambda b: -((b.me() or {}).get("gold") or 0))
        if not payers:
            return
        d.step(f"scribe revives {bot.name}")
        got = await _reply(payers[0], {"type": "scribe_revive", "target_id": bot.hero_id})
        await d.settle()
        if d.srv.table.state.creatures[bot.hero_id].dead:
            d.report.notes.append(f"{bot.name} stays dead: {got.get('text', got['type'])}")
        else:
            d.report.gear["revived"] += 1


async def level_all(d: "Director") -> None:
    for bot in living(d):
        for _ in range(MAX_LEVELS_AT_ONCE):
            result = await level_up_bot(bot, main=main_ability(bot.class_index))
            if result == NO_LEVEL:
                break
            if result != "ok":
                d.report.fail(f"level up refused for {bot.name} ({bot.class_index}): {result}")
                break
    await d.settle()
    levels = [c["level"] for c in d.state().get("party", []) if c.get("level")]
    d.report.level = max([d.report.level, *levels])


async def best_at(d: "Director", skill: str) -> Bot | None:
    """The living hero with the best `skill` bonus on its own sheet (who should roll it)."""

    def bonus(bot: Bot) -> int:
        lines = (bot.sheet or {}).get("skills", [])
        return next((int(x["bonus"]) for x in lines if x["skill"] == skill), -99)

    up = living(d)
    for bot in up:
        await bot.gear_uses()
    return max(up, key=bonus, default=None)


def _searcher(d: "Director") -> Bot | None:
    up = living(d)
    return next((b for b in up if b.role == "explorer"), up[0] if up else None)


async def search_here(d: "Director") -> None:
    bot = _searcher(d)
    if bot is None:
        return
    d.step(f"search {scene_of(d.state()).get('node_id')}")
    await bot.submit(SEARCH_TEXT, d.timeout)
    await d.settle()


async def pick_up_all(d: "Director") -> None:
    for name in list(scene_of(d.state()).get("items", []))[:MAX_PICKUPS]:
        bot = _searcher(d)
        if bot is None:
            return
        await bot.submit(f"I pick up the {name}", d.timeout)
        await d.settle()


def _peace_name(d: "Director") -> str | None:
    state = d.srv.table.state
    region = region_of(state, scene_of(d.state()).get("node_id"))
    campaign = state.campaign
    if region is None or campaign is None:
        return None
    act = next(a for a in campaign.plan.acts if a.region.id == region.id)
    routes = act.main.routes if act.main is not None else ()
    peace = next((r for r in routes if r.kind is RouteKind.PEACE), None)
    items = [s.item for s in peace.steps if s.item] if peace is not None else []
    return items[0] if items else None


async def peace_item(d: "Director") -> tuple[Bot, str] | None:
    """(carrier, keepsake id) of the region's Peace item, from the heroes' own sheets."""
    name = _peace_name(d)
    if name is None:
        return None
    for bot in living(d):
        await bot.gear_uses()
        found = [k for k in (bot.sheet or {}).get("keepsakes", []) if k["name"] == name]
        if found:
            return bot, found[0]["id"]
    return None


async def give(d: "Director", carrier: Bot, keepsake_id: str) -> None:
    region = region_of(d.srv.table.state, scene_of(d.state()).get("node_id"))
    if region is None:
        return
    d.step(f"give {keepsake_id} to the master")
    send = {"type": "give", "npc_id": boss_npc_id(region), "item_id": keepsake_id}
    mark = carrier.conn.mark()
    await carrier.conn.send(send)
    await carrier.conn.wait_for(lambda m: m["type"] in ("error", "narration_done"), d.timeout, mark)
    await d.settle()
