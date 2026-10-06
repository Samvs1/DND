"""One simulated seed end to end, and the many-seed loop with its summary lines.

`run_seed` starts a fresh server (fake LLM unless `live_ai`) over a temp saves folder, seats the
three bots, runs the `Director` phases and then checks: server errors, snapshot invariants on
every received snapshot, privacy of everything received, and replay of the saved log.

Public API: `run_seed`, `run_all`, `SimOptions`.
"""

import asyncio
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path

from scripts.sim.checks import (
    engine_invariants,
    message_texts,
    privacy_leaks,
    public_invariants,
    replay_problems,
)
from scripts.sim.fight import answer_offer, fight
from scripts.sim.flow import Director
from scripts.sim.recovery import recover
from scripts.sim.report import Report
from scripts.sim.server import SimServer
from scripts.sim.setup import Party, seat_party


@dataclass(frozen=True)
class SimOptions:
    live_ai: bool = False
    timeout: float = 60.0
    verbose: bool = False


async def _play(srv: SimServer, report: Report, party: Party, opts: SimOptions) -> None:
    d = Director(srv, party, report, opts.timeout, report.seed)
    await d.start_campaign()
    await d.probes()
    await d.explore_round("opening")
    visited: list[str] = []
    while (name := d.spoke_to_visit()) is not None and len(visited) < 3:
        visited.append(name)
        await recover(d)
        if not await d.travel(name):
            break
        if d.state().get("offer") is not None and not await fight(d):
            break
        await d.explore_round(f"at {name}")
        if len(visited) == 1:
            await d.short_rest()
        await d.return_to_hub()
    await recover(d)
    await d.level_ups()
    await d.to_gateway(visited)
    if d.state().get("offer") is not None:
        await answer_offer(d, "escape")


def _post_checks(srv: SimServer, report: Report, party: Party | None) -> None:
    report.step = "final checks"
    for error in srv.capture.errors:
        report.fail(f"server error: {error[:1500]}")
    if party is None:
        return
    for bot in party.bots:
        for msg in bot.conn.log:
            if msg["type"] == "snapshot":
                for problem in public_invariants(msg["state"]):
                    report.fail(f"snapshot invariant ({bot.name}, seq {msg['seq']}): {problem}")
                    break
    texts = message_texts([bot.conn.log for bot in party.bots])
    for leak in privacy_leaks(srv.table.state, texts):
        report.fail(leak)
    for problem in engine_invariants(srv.table.state):
        report.fail(f"engine invariant at the end: {problem}")


async def run_seed(seed: int, opts: SimOptions) -> Report:
    report = Report(seed, verbose=opts.verbose)
    party: Party | None = None
    with tempfile.TemporaryDirectory(prefix=f"aidm-sim-{seed}-") as tmp:
        saves = Path(tmp) / "saves"
        srv = SimServer(seed, saves, live_ai=opts.live_ai)
        await srv.start()
        try:
            party = await seat_party(srv.url, seed, report)
            await _play(srv, report, party, opts)
        except Exception as exc:
            tb = "".join(traceback.format_exception(exc)[-4:])
            report.fail(f"director stopped: {type(exc).__name__}: {exc}\n{tb}")
        finally:
            if party is not None:
                await asyncio.gather(*(b.conn.close() for b in party.bots))
            await srv.stop()
        _post_checks(srv, report, party)
        report.step = "replay"
        for problem in replay_problems(saves, srv.state.campaign_id, srv.table.state):
            report.fail(problem)
    return report


async def run_all(seeds: int, opts: SimOptions) -> list[Report]:
    reports: list[Report] = []
    for seed in range(1, seeds + 1):
        report = await run_seed(seed, opts)
        print(report.summary(), flush=True)
        for note in report.notes:
            report.say(f"note: {note}")
        reports.append(report)
    return reports
