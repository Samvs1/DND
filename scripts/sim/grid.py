"""Full-campaign runs per play style and party shape (M29.2), and the grid over both.

`run_campaign(seed, style, shape, opts, out, scale)` starts a fresh server (fake storyteller) over a
temp saves folder, seats the shape (`scripts.sim.shapes`), plays the campaign to the epilogue
(`scripts.sim.campaign`) and runs the same end checks as the M9.1 run (server errors, snapshot
and engine invariants, privacy, replay of the saved log, no refused-use loops). With `out` the
save is copied to `out/<style>-<shape>-s<seed>/` with a `tags.json` ({style, party, seed,
outcome, retries, level, seconds}) so `scripts/balance_report.py out` groups the runs. `scale`
is the host's monster difficulty (HP and damage x scale): 1.0 for the baseline, lower in tests.

Public API: `run_campaign`, `run_grid`, `export_save`.
"""

import json
import shutil
import tempfile
import time
import traceback
from collections import Counter
from pathlib import Path

from scripts.sim.campaign import play_campaign
from scripts.sim.checks import replay_problems
from scripts.sim.flow import Director
from scripts.sim.gear import refusal_runs
from scripts.sim.report import Report
from scripts.sim.run import SimOptions, post_checks
from scripts.sim.server import SimServer
from scripts.sim.setup import Party
from scripts.sim.shapes import seat_shape
from scripts.sim.styles import style_of


def export_save(saves: Path, campaign_id: str, out: Path, report: Report) -> Path:
    """Copy the run's save next to its tags; returns the run folder."""
    dest = out / f"{report.style}-{report.shape}-s{report.seed}"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(saves / campaign_id, dest)
    tags = {
        "style": report.style,
        "party": report.shape,
        "seed": report.seed,
        "outcome": report.outcome,
        "retries": report.retries,
        "level": report.level,
        "seconds": round(report.seconds, 1),
        "failures": len(report.failures),
    }
    (dest / "tags.json").write_text(json.dumps(tags, indent=2), encoding="utf-8")
    return dest


def _errors(party: Party) -> Counter[str]:
    """Typed errors the bots received, by code and refusal (a diagnostic note per run)."""
    seen: Counter[str] = Counter()
    for bot in party.bots:
        for m in bot.conn.log:
            if m["type"] == "error":
                seen[f"{m.get('code')}:{m.get('refusal') or ''}"] += 1
    return seen


async def _play(srv: SimServer, report: Report, opts: SimOptions, scale: float) -> Party | None:
    party: Party | None = None
    try:
        party = await seat_shape(srv.url, report.seed, report.shape, report)
        d = Director(srv, party, report, opts.wait, report.seed)
        if scale != 1.0:  # the host's difficulty setting (tests only; the baseline uses 1.0)
            send = {"type": "host_difficulty", "monster_hp": scale, "monster_damage": scale}
            await d.host.conn.send(send)
            await d.settle()
        await play_campaign(d, style_of(report.style))
    except Exception as exc:
        tb = "".join(traceback.format_exception(exc)[-4:])
        report.fail(f"director stopped: {type(exc).__name__}: {exc}\n{tb}")
    return party


async def run_campaign(
    seed: int,
    style: str,
    shape: str,
    opts: SimOptions,
    out: Path | None = None,
    scale: float = 1.0,
) -> Report:
    report = Report(seed, verbose=opts.verbose, style=style, shape=shape)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"aidm-camp-{seed}-") as tmp:
        saves = Path(tmp) / "saves"
        srv = SimServer(seed, saves, live_ai=opts.live_ai)
        await srv.start()
        party: Party | None = None
        try:
            party = await _play(srv, report, opts, scale)
        finally:
            if party is not None:
                for bot in party.bots:
                    await bot.conn.close()
            await srv.stop()
        if party is not None:
            report.notes.append(f"errors seen: {dict(_errors(party))}")
        post_checks(srv, report, party)
        report.step = "refusals"
        for problem in refusal_runs([entry.event for entry in srv.table.log]):
            report.fail(problem)
        report.step = "replay"
        for problem in replay_problems(saves, srv.state.campaign_id, srv.table.state):
            report.fail(problem)
        report.seconds = time.monotonic() - started
        if out is not None:
            export_save(saves, srv.state.campaign_id, out, report)
    return report


async def run_grid(
    styles: list[str],
    shapes: list[str],
    seeds: list[int],
    opts: SimOptions,
    out: Path | None,
) -> list[Report]:
    reports: list[Report] = []
    for style in styles:
        for shape in shapes:
            for seed in seeds:
                report = await run_campaign(seed, style, shape, opts, out)
                print(report.summary(), flush=True)
                for note in report.notes:
                    report.say(f"note: {note}", force=note.startswith("errors seen"))
                reports.append(report)
    return reports
