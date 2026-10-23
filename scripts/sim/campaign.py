"""A full campaign to the epilogue for one play style (M29.2, docs/next/GOAL_BALANCE.md).

Per act: shop at the arrival (per style), visit every spoke and answer its encounter offer the
style's way (fight, surprise, parley), revive the dead, take the level-ups, search and pick up
(per style), rest by the style's thresholds, camp before the master (per style), walk to the
gateway and deal with the master: fight it, or (the Peace way) parley and hand over the item
the region's main quest hides. A resolved region opens the next act's arrival; after the last
one the finale card is answered and the epilogue must arrive. A party that loses a fight for
good after the retries ends the run with a balance outcome (`report.outcome`), not a failure;
a stuck turn, a softlock or a crash is a failure.

Public API: `play_campaign(d, style)`.
"""

import contextlib
from typing import TYPE_CHECKING

from aidm.models.protocol_views import TablePhase
from aidm.rules.progression import region_of
from scripts.sim.campaign_steps import (
    best_at,
    give,
    level_all,
    peace_item,
    pick_up_all,
    revive,
    search_here,
    shop,
    spent,
)
from scripts.sim.explore import scene_of
from scripts.sim.fight import answer_offer
from scripts.sim.recovery import camp, recover
from scripts.sim.styles import Style

if TYPE_CHECKING:
    from scripts.sim.flow import Director

MAX_BOSS_VISITS = 2  # a parley that did not end it, then a fight
EPILOGUE_WAIT = 3  # times the step timeout


def _defeated(d: "Director") -> bool:
    return d.srv.table.phase is TablePhase.DEFEATED


def _node(d: "Director") -> str:
    return str(scene_of(d.state()).get("node_id", ""))


def _resolved(d: "Director", act: int) -> bool:
    campaign = d.srv.table.state.campaign
    if campaign is None:
        return False
    return campaign.plan.acts[act - 1].region.id in campaign.resolved


async def _after(d: "Director", style: Style) -> None:
    """What a table does when the dust settles: the Scribe, level-ups, a search, the loot."""
    await revive(d)
    await level_all(d)
    if style.search:
        await search_here(d)
    await pick_up_all(d)
    if style.talk:
        await d.explore_round(f"at {_node(d)}")


async def _answer(d: "Director", choice: str) -> bool:
    """Answer the pending offer (if any); False when the party lost for good. A parley is
    pressed by the hero with the best Persuasion (the one who rolls it)."""
    if d.state().get("offer") is not None:
        sender = await best_at(d, "persuasion") if choice == "parley" else None
        await answer_offer(d, choice, sender)
    return not _defeated(d)


async def _place(d: "Director", style: Style, name: str) -> bool:
    await recover(d, style.short_below, style.long_below)
    if not await d.travel(name):
        return False
    if not await _answer(d, style.offer):
        return False
    await _after(d, style)
    return True


async def _exit_to(d: "Director", node_id: str) -> bool:
    exits = scene_of(d.state()).get("exits", [])
    name = next((e["name"] for e in exits if e["node_id"] == node_id and not e["locked"]), None)
    if name is None:
        d.report.fail(f"no open way from {_node(d)} to {node_id}: {exits}")
        return False
    return await d.travel(name)


async def _to_gateway(d: "Director", act: int, spoke: str) -> bool:
    campaign = d.srv.table.state.campaign
    assert campaign is not None
    gateway = campaign.plan.acts[act - 1].region.gateway.id
    if _node(d) == gateway:
        return True
    if _node(d) == d.hub and not await d.travel(spoke):
        return False
    if d.state().get("offer") is not None and not await _answer(d, "fight"):
        return False
    return await _exit_to(d, gateway)


async def _before_boss(d: "Director", style: Style) -> None:
    await recover(d, style.short_below, style.long_below)
    if style.camp_before_boss and spent(d):
        await camp(d)
    await level_all(d)


async def _boss_once(d: "Director", style: Style, act: int, visit: int) -> bool:
    """One walk to the master; True when the party still stands (resolved or not)."""
    carrier = await peace_item(d) if style.peace and visit == 0 else None
    choice = style.boss
    if choice == "parley" and carrier is None:
        choice = "fight"  # without the item the talk cannot end it: the table fights
    d.step(f"act {act} master: {choice}")
    if not await _answer(d, choice):
        return False
    if carrier is not None and not d.srv.table.in_combat and not _resolved(d, act):
        await give(d, *carrier)
    await revive(d)
    await level_all(d)
    return True


async def _boss(d: "Director", style: Style, act: int, spoke: str) -> bool:
    for visit in range(MAX_BOSS_VISITS):
        if not await _to_gateway(d, act, spoke):
            return False
        if d.state().get("offer") is None and not _resolved(d, act):
            d.report.fail(f"act {act}: no master to face at the gateway {_node(d)}")
            return False
        if not await _boss_once(d, style, act, visit):
            return False
        if _resolved(d, act):
            return True
        await recover(d, style.short_below, style.long_below)
        if not await _exit_to(d, _spoke_id(d, act, spoke)):
            return False
    d.report.fail(f"act {act}: the region was not resolved after {MAX_BOSS_VISITS} visits")
    return False


def _spoke_id(d: "Director", act: int, spoke_name: str) -> str:
    campaign = d.srv.table.state.campaign
    assert campaign is not None
    spokes = campaign.plan.acts[act - 1].region.spokes
    return next((s.id for s in spokes if s.name == spoke_name), spokes[0].id)


async def _act(d: "Director", style: Style, act: int) -> bool:
    d.hub = _node(d)
    d.step(f"act {act} arrival {d.hub}")
    await shop(d, style, first=act == 1)
    await d.explore_round(f"act {act} arrival")
    spoke = ""
    while (name := d.spoke_to_visit()) is not None:
        spoke = name
        if not await _place(d, style, name):
            return False
        await d.return_to_hub()
    if not spoke:
        d.report.fail(f"act {act}: no spoke to visit from {d.hub}")
        return False
    await _before_boss(d, style)
    return await _boss(d, style, act, spoke)


async def _next_region(d: "Director", act: int) -> bool:
    campaign = d.srv.table.state.campaign
    assert campaign is not None
    arrival = campaign.plan.acts[act].region.arrival.id
    d.step(f"to act {act + 1}")
    if not await _exit_to(d, arrival):
        return False
    region = region_of(d.srv.table.state, _node(d))
    return region is not None and region.arrival.id == arrival


async def _finale(d: "Director") -> None:
    d.step("finale")
    card = d.state().get("finale")
    if not card or not card.get("options"):
        d.report.fail(
            f"no finale card after the last region (complete={d.state().get('complete')})"
        )
        return
    option = d.rng.choice(card["options"])["id"]
    bot = d.proposer(d.party.fighter)
    mark = bot.conn.mark()
    await bot.conn.send({"type": "choose_finale", "option_id": option, "confirm": True})
    with contextlib.suppress(TimeoutError):
        await bot.conn.wait_for(lambda m: m["type"] == "epilogue", d.timeout * EPILOGUE_WAIT, mark)
    await d.settle()
    if not d.state().get("complete") or not d.state().get("epilogue"):
        d.report.fail(f"the finale {option} was chosen and no epilogue came")
        return
    d.report.outcome = "epilogue"


async def play_campaign(d: "Director", style: Style) -> None:
    d.campaign = True
    await d.start_campaign()
    for act in (1, 2, 3):
        d.report.outcome = f"act {act}"
        if not await _act(d, style, act):
            if _defeated(d):
                d.report.outcome = f"defeated act {act} at {_node(d)}"
            return
        if act < 3 and not await _next_region(d, act):
            d.report.fail(f"act {act}: the way to act {act + 1} did not open")
            return
    await _finale(d)
