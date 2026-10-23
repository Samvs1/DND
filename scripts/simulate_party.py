"""Party simulation (SPEC 13 Simulation, M9.1): bot players over real websockets, real server.

    python scripts/simulate_party.py --seeds 5 [--live-ai] [--timeout S] [--verbose]
    python scripts/simulate_party.py --style balanced[,talker]|all --party classic[,solo]|all
        --seeds 5 [--first-seed N] [--out saves/balance]

Without --style/--party (the M9.1 run), per seed: a fresh in-process server (fake LLM unless
--live-ai) over a temp saves folder, an aggressive fighter, a chatty explorer and a chaotic
player (invalid commands, injections, abuse) create heroes, explore, travel by vote, fight the
spoke offers at the default difficulty, take a short and a long rest (from the starting camp
supplies), level up on earned XP (kills plus spoke milestones; no XP is injected) and walk to
the region gateway. Asserts: no server-side exception, no silent turn, hp and slot invariants,
no private text in any client message, a level-up and both rests reached by play, and the saved
event log replays to the final state. Prints one line per seed and
`SIMULATION OK seeds=<n> turns=<t> combats=<c> min_level=<l>` (exit 0) or `SIMULATION FAILED`.

With --style or --party (M29.2, docs/next/GOAL_BALANCE.md), each (style, party, seed) plays a
FULL campaign to the epilogue on the fake storyteller (`scripts.sim.campaign`) with the same
end checks, and its save is written to `--out/<style>-<party>-s<seed>/` with a `tags.json` for
`scripts/balance_report.py`. Styles: balanced, aggressive, cautious, talker, cunning, spender,
hoarder. Parties: classic, martial, casters, solo, duo. Prints one line per run and
`CAMPAIGNS OK runs=<n> epilogue=<e> defeated=<d>` (exit 0) or `CAMPAIGNS FAILED ...` (exit 1).
A run that loses a fight for good is a balance outcome, not a failure.
"""

import argparse
import asyncio
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "saves" / "balance"


def _args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate a party of bot players.")
    parser.add_argument("--seeds", type=int, default=1, help="number of seeds")
    parser.add_argument("--first-seed", type=int, default=1, help="the first seed (campaigns)")
    parser.add_argument("--live-ai", action="store_true", help="use the real DeepSeek model")
    parser.add_argument(
        "--timeout", type=float, default=None, help="seconds per awaited step (60, live 300)"
    )
    parser.add_argument("--verbose", action="store_true", help="log every step")
    parser.add_argument("--style", default=None, help="play styles a,b or 'all' (campaigns)")
    parser.add_argument("--party", default=None, help="party shapes a,b or 'all' (campaigns)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="where campaign saves go")
    return parser.parse_args(argv)


def _print_failures(reports: list[object]) -> None:
    for report in reports:
        for reason in getattr(report, "failures", []):
            print("  " + reason.encode("ascii", "replace").decode("ascii").replace("\n", "\n    "))


def _campaigns(args: argparse.Namespace) -> int:
    from scripts.sim.grid import run_grid
    from scripts.sim.run import SimOptions
    from scripts.sim.shapes import SHAPES
    from scripts.sim.styles import STYLES

    style: str = args.style or "balanced"
    party: str = args.party or "classic"
    styles: list[str] = list(STYLES) if style == "all" else [str(x) for x in style.split(",")]
    shapes: list[str] = list(SHAPES) if party == "all" else [str(x) for x in party.split(",")]
    seeds = list(range(args.first_seed, args.first_seed + args.seeds))
    opts = SimOptions(live_ai=args.live_ai, timeout=args.timeout, verbose=args.verbose)
    reports = asyncio.run(run_grid(styles, shapes, seeds, opts, args.out))
    failed = [r for r in reports if not r.ok]
    done = sum(r.outcome == "epilogue" for r in reports)
    lost = sum(r.outcome.startswith("defeated") for r in reports)
    tail = f"runs={len(reports)} epilogue={done} defeated={lost}"
    if not failed:
        print(f"CAMPAIGNS OK {tail}")
        return 0
    print(f"CAMPAIGNS FAILED failed={len(failed)} {tail}")
    _print_failures(list(failed))
    return 1


def main(argv: list[str] | None = None) -> int:
    from scripts.sim.run import SimOptions, run_all

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _args(argv)
    if args.style is not None or args.party is not None:
        return _campaigns(args)
    opts = SimOptions(live_ai=args.live_ai, timeout=args.timeout, verbose=args.verbose)
    reports = asyncio.run(run_all(args.seeds, opts))
    turns = sum(r.turns for r in reports)
    combats = sum(r.combats for r in reports)
    failed = [r for r in reports if not r.ok]
    if not failed:
        level = min(r.level for r in reports)
        print(f"SIMULATION OK seeds={args.seeds} turns={turns} combats={combats} min_level={level}")
        return 0
    print(
        f"SIMULATION FAILED seeds={args.seeds} failed={len(failed)} turns={turns} combats={combats}"
    )
    _print_failures(list(failed))
    return 1


if __name__ == "__main__":
    sys.exit(main())
