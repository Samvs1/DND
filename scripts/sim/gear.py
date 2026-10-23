"""The gear phases of the director (M27.10, docs/next/GOAL_ITEMS.md "Done means").

- `stock_up`: at the hub before the first trip the party browses the wares (a ready vote) and the
  fighter (the sturdiest hero, in the thick of it next to a fallen friend) buys a healer's kit
  (a general store always has one); the fighter's dungeoneer's pack holds the torches, the
  rogue's burglar's pack the oil.
- `dark_place`: out of a fight in a dark place (the scene says `dark`): every lit light is put
  out, a search rolls with the *Darkness* disadvantage, the torch bearer types "I light my torch",
  the same search rolls without it, and the light is put out again before the next dark place.
- `gear_failures`: what the engine's event log must show at the end of a seed: a light lit and
  put out, a combat item used in the fights, the healer's kit used whenever an ally lay dying on
  the kit bearer's turn, and no refused use repeated over and over. Uses made in a fight that
  ended in a retried wipe live in the save's `events.<n>.defeat` tails (cut from the live log),
  so those count too (M29.6: a tuned spoke wiped the party mid-kit in seed 3).

Public API: `stock_up`, `dark_place`, `gear_failures`, `refusal_runs`, `tail_uses`.
"""

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from aidm.models.item_events import ItemUsed, ItemUseRefused, LightEnded, LightLit
from aidm.rules.light import DARKNESS, DOUSED
from aidm.session.metrics import load_defeat_tails
from scripts.sim.bot import Bot
from scripts.sim.checks import hero_up
from scripts.sim.explore import scene_of
from scripts.sim.fake_dm import SEARCH_TEXT
from scripts.sim.gear_fight import COMBAT_ITEM_USES, KIT_USE

if TYPE_CHECKING:
    from scripts.sim.flow import Director

KIT = "healers-kit"
TORCH = "torch"
MAX_SAME_REFUSALS = 2  # the same refused use twice in a row is a retry; three is a loop


async def stock_up(d: "Director") -> None:
    buyer = d.party.fighter
    d.step("stock up")
    mark = buyer.conn.mark()
    if not await d.propose(d.proposer(d.party.fighter), "I browse the wares"):
        d.report.notes.append("the shop vote did not pass")
        return
    stock = next((m for m in reversed(buyer.conn.log[mark:]) if m["type"] == "shop_stock"), None)
    line = next((s for s in (stock or {}).get("stock", []) if s["item_id"] == KIT), None)
    gold = (buyer.me() or {}).get("gold") or 0
    if stock is None or line is None or gold < line["price_gp"]:
        d.report.notes.append(f"no healer's kit bought (gold {gold}, on sale {line is not None})")
        return
    send = {"type": "shop_buy", "npc_id": stock["npc_id"], "item_id": KIT, "qty": 1}
    mark = buyer.conn.mark()
    await buyer.conn.send(send)
    await buyer.conn.wait_for(lambda m: m["type"] in ("error", "notice", "snapshot"), 15.0, mark)
    await d.settle()
    d.report.gear["kit_bought"] += 1


def _alive(d: "Director", bot: Bot) -> bool:
    return hero_up(d.srv.table.state, bot.hero_id)


def _carries(d: "Director", bot: Bot, item: str) -> bool:
    hero = d.srv.table.state.creatures.get(bot.hero_id)
    return (
        hero is not None and hero.pc is not None and any(e.item == item for e in hero.pc.inventory)
    )


async def _search(d: "Director", bot: Bot) -> tuple[str, ...] | None:
    """The searcher's `adv_why` on the check the search rolled, None when nothing rolled."""
    mark = bot.conn.mark()
    await bot.submit(SEARCH_TEXT, d.timeout)
    await d.settle()
    rolls = [
        m["dice"]
        for m in bot.conn.log[mark:]
        if m["type"] == "dice_roll" and m["dice"].get("roller_id") == bot.hero_id
    ]
    return tuple(rolls[-1].get("adv_why", ())) if rolls else None


async def _put_out(d: "Director", bot: Bot) -> bool:
    light = (bot.me() or {}).get("light") or ""
    if not light:
        return False
    await bot.submit(f"I put out my {light.lower()}", d.timeout)
    await d.settle()
    if (bot.me() or {}).get("light"):
        d.report.fail(f"{bot.name} typed 'put out my {light.lower()}' and the light still burns")
        return False
    d.report.gear["doused"] += 1
    return True


async def dark_place(d: "Director") -> None:
    if not scene_of(d.state()).get("dark"):
        return
    d.step(f"dark place {scene_of(d.state()).get('node_id')}")
    d.report.gear["dark_places"] += 1
    for bot in d.party.bots:
        await _put_out(d, bot)
    living = [b for b in d.party.bots if _alive(d, b)]
    searcher = next((b for b in [d.party.explorer, *living] if _alive(d, b)), None)
    bearer = next((b for b in [d.party.fighter, *living] if _carries(d, b, TORCH)), None)
    if searcher is None or bearer is None or not _alive(d, bearer):
        d.report.notes.append("no living searcher or torch bearer in the dark place")
        return
    before = await _search(d, searcher)
    if before is None or DARKNESS not in before:
        d.report.fail(f"a search in a dark unlit place rolled {before} (no {DARKNESS})")
    await bearer.submit("I light my torch", d.timeout)
    await d.settle()
    if (bearer.me() or {}).get("light") != "Torch":
        d.report.fail(f"{bearer.name} typed 'I light my torch' and no torch burns")
        return
    d.report.gear["torch_lit"] += 1
    after = await _search(d, searcher)
    if after is None or DARKNESS in after:
        d.report.fail(f"a search in the torch-lit place rolled {after}")
    await _put_out(d, bearer)


def refusal_runs(events: list[object]) -> list[str]:
    """Refused uses repeated more than MAX_SAME_REFUSALS times in a row by the same hero."""
    out: list[str] = []
    run: tuple[str, str] | None = None
    count = 0
    for event in events:
        if not isinstance(event, ItemUseRefused):
            continue
        key = (event.creature_id, event.message)
        count = count + 1 if key == run else 1
        run = key
        if count == MAX_SAME_REFUSALS + 1:
            out.append(f"refused-use loop: {key[0]} {key[1][:80]!r} x{count}")
    return out


def tail_uses(folder: Path, use_id: str) -> int:
    """`ItemUsed` of `use_id` in the save's retried-wipe tails (`events.<n>.defeat`)."""
    tails = load_defeat_tails(folder) if folder.is_dir() else []
    return sum(
        1
        for _, events in tails
        for e in events
        if e.get("type") == "item_used" and e.get("use_id") == use_id
    )


def _save(d: "Director") -> Path:
    return d.srv.saves_dir / d.srv.table.state.campaign_id


def gear_failures(d: "Director") -> list[str]:
    events = [entry.event for entry in d.srv.table.log]
    used = Counter(e.use_id for e in events if isinstance(e, ItemUsed))
    out = refusal_runs(list(events))
    if d.report.gear["dark_places"] == 0:
        out.append("no dark place was explored out of a fight")
    if not any(isinstance(e, LightLit) for e in events):
        out.append("no light was lit")
    if not any(isinstance(e, LightEnded) and e.reason == DOUSED for e in events):
        out.append("no light was put out")
    if d.report.combats and not any(u in COMBAT_ITEM_USES for u in used):
        out.append(f"no combat item used in {d.report.combats} fights ({dict(used)})")
    chances = sum(b.plan.kit_chances for b in d.party.bots)
    if chances and not used[KIT_USE] + tail_uses(_save(d), KIT_USE):
        out.append(f"an ally lay dying on the kit bearer's turn {chances}x; the kit was never used")
    d.report.gear["kit_chances"] += chances
    return out
