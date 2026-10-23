"""Combat orchestration: answer the encounter offer and play the fight to its end.

Every bot runs its own `fight` task (answer each `turn_prompt` for its hero) while the chaotic
player fires invalid combat commands out of turn; each of those must get a typed error.
A party wipe (M11.1) puts the table in the DEFEATED phase: the host bot then chooses
`defeat_retry` (back to the fight-start checkpoint, reseeded dice) up to `MAX_RETRIES` times,
and the fight is played again; a party that still loses fails the seed.

Public API: `answer_offer`, `fight`.
"""

import asyncio
import contextlib
from typing import TYPE_CHECKING

from aidm.models.protocol_views import TablePhase
from scripts.sim.chaos import bogus_combat
from scripts.sim.client import Msg

if TYPE_CHECKING:
    from scripts.sim.bot import Bot
    from scripts.sim.flow import Director


MAX_RETRIES = 3
REPLY_TYPES = frozenset({"snapshot", "error", "event", "notice"})


def _combat_off(m: Msg) -> bool:
    return m["type"] == "combat_state" and m.get("combat") is None


async def _noise(d: "Director", stop: asyncio.Event) -> None:
    bot, n = d.party.chaos, 0
    if bot is None:  # M29.2: a shape without a chaotic player makes no noise
        return
    while not stop.is_set():
        await asyncio.sleep(1.5)
        n += 1
        mark = bot.conn.mark()
        await bot.conn.send({"type": "combat_command", "command": bogus_combat(bot.hero_id, n)})
        try:
            await bot.conn.wait_for(lambda m: m["type"] == "error", 15.0 * bot.patience, mark)
        except TimeoutError:
            d.report.fail("invalid combat command got no typed error")


async def _play_out(d: "Director", send: Msg, *, fight: bool, sender: "Bot | None" = None) -> bool:
    """Send `send` (from `sender`, else the host) while every bot answers its turn prompts;
    True when a fight was played out."""
    stop = asyncio.Event()
    tasks = [asyncio.create_task(b.fight(stop)) for b in d.party.bots]
    tasks.append(asyncio.create_task(_noise(d, stop)))
    conn = (sender or d.host).conn
    mark = conn.mark()
    fought = False
    try:
        await conn.send(send)
        with contextlib.suppress(TimeoutError):  # settle only once the table has the message
            await conn.wait_for(lambda m: m["type"] in REPLY_TYPES, d.timeout, mark)
        await d.srv.table.settle()
        if fight or d.srv.table.in_combat:
            await conn.wait_idx(_combat_off, d.timeout * 6, mark)
            fought = True
    except TimeoutError as exc:
        d.report.fail(f"combat did not finish: {exc}; {d.party_line()}")
        return False
    finally:
        stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)
    for m in conn.log[mark:]:
        if m["type"] == "event":
            d.report.say(f"   | {m['line'][:150]}")
    return fought


async def _retry_defeats(d: "Director") -> None:
    for attempt in range(1, MAX_RETRIES + 1):
        if d.srv.table.phase is not TablePhase.DEFEATED:
            return
        d.report.retries += 1
        d.report.notes.append(f"party wiped; retry {attempt} from the last checkpoint")
        d.step(f"defeat retry {attempt}")
        await _play_out(d, {"type": "defeat_retry"}, fight=False)
        await d.settle()
    if d.srv.table.phase is not TablePhase.DEFEATED:
        return
    if d.campaign:  # M29.2: a campaign that loses a fight for good is a balance outcome
        d.report.outcome = "defeated"
        return
    d.report.fail(f"the party was still defeated after {MAX_RETRIES} retries")


async def answer_offer(d: "Director", choice: str = "fight", sender: "Bot | None" = None) -> bool:
    """Answer the pending offer (M29.2: from `sender`, the hero who rolls a parley); if a fight
    follows, play it out. True when one was fought."""
    offer = d.state().get("offer")
    if offer is None:
        d.report.fail("no encounter offer to answer")
        return False
    d.step(f"offer {choice} at {offer['node_id']} vs {','.join(offer['foes'])}")
    send = {"type": "answer_offer", "choice": choice}
    fought = await _play_out(d, send, fight=choice == "fight", sender=sender)
    if fought:
        d.report.combats += 1
        d.fights += 1
    await d.settle()
    await _retry_defeats(d)
    return fought and d.srv.table.phase is not TablePhase.DEFEATED


async def fight(d: "Director") -> bool:
    return await answer_offer(d, "fight")
