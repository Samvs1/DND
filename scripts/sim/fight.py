"""Combat orchestration: answer the encounter offer and play the fight to its end.

Every bot runs its own `fight` task (answer each `turn_prompt` for its hero) while the chaotic
player fires invalid combat commands out of turn; each of those must get a typed error.

Public API: `answer_offer`, `fight`.
"""

import asyncio
from typing import TYPE_CHECKING

from scripts.sim.chaos import bogus_combat
from scripts.sim.client import Msg

if TYPE_CHECKING:
    from scripts.sim.flow import Director


def _combat_off(m: Msg) -> bool:
    return m["type"] == "combat_state" and m.get("combat") is None


async def _noise(d: "Director", stop: asyncio.Event) -> None:
    bot, n = d.party.chaos, 0
    while not stop.is_set():
        await asyncio.sleep(1.5)
        n += 1
        mark = bot.conn.mark()
        await bot.conn.send({"type": "combat_command", "command": bogus_combat(bot.hero_id, n)})
        try:
            await bot.conn.wait_for(lambda m: m["type"] == "error", 15.0, mark)
        except TimeoutError:
            d.report.fail("invalid combat command got no typed error")


async def answer_offer(d: "Director", choice: str = "fight") -> bool:
    """Answer the pending offer; if a fight follows, play it out. True when one was fought."""
    offer = d.state().get("offer")
    if offer is None:
        d.report.fail("no encounter offer to answer")
        return False
    d.step(f"offer {choice} at {offer['node_id']} vs {','.join(offer['foes'])}")
    stop = asyncio.Event()
    tasks = [asyncio.create_task(b.fight(stop)) for b in d.party.bots]
    tasks.append(asyncio.create_task(_noise(d, stop)))
    conn = d.host.conn
    mark = conn.mark()
    fought = False
    try:
        await conn.send({"type": "answer_offer", "choice": choice})
        await d.srv.table.settle()
        if choice == "fight" or d.srv.table.in_combat:
            await conn.wait_idx(_combat_off, d.timeout * 6, mark)
            fought = True
    except TimeoutError as exc:
        d.report.fail(f"combat did not finish: {exc}; {d.party_line()}")
        return False
    finally:
        stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)
    if fought:
        d.report.combats += 1
        d.fights += 1
        for m in conn.log[mark:]:
            if m["type"] == "event":
                d.report.say(f"   | {m['line'][:150]}")
    await d.settle()
    return fought


async def fight(d: "Director") -> bool:
    return await answer_offer(d, "fight")
