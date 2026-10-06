"""Party simulation (SPEC 13 Simulation, M9.1): three real-websocket bots against the real server.

    python scripts/simulate_party.py --seeds 5 [--live-ai] [--timeout 60] [--verbose]

Per seed: a fresh in-process server (fake LLM unless --live-ai) over a temp saves folder, an
aggressive fighter, a chatty explorer and a chaotic player (invalid commands, injections, abuse)
create heroes, explore, travel by vote, fight a full combat, rest, level up and walk to the
region gateway. Asserts: no server-side exception, no silent turn, hp and slot invariants, no
private text in any client message, and the saved event log replays to the final state.
Prints one line per seed and `SIMULATION OK seeds=<n> turns=<t> combats=<c>` (exit 0) or
`SIMULATION FAILED ...` with the reasons (exit 1).
"""

import argparse
import asyncio
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from scripts.sim.run import SimOptions, run_all

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Simulate a party of three bot players.")
    parser.add_argument("--seeds", type=int, default=1, help="number of seeds (1..N)")
    parser.add_argument("--live-ai", action="store_true", help="use the real DeepSeek model")
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds per awaited step")
    parser.add_argument("--verbose", action="store_true", help="log every step")
    args = parser.parse_args(argv)
    opts = SimOptions(live_ai=args.live_ai, timeout=args.timeout, verbose=args.verbose)
    reports = asyncio.run(run_all(args.seeds, opts))
    turns = sum(r.turns for r in reports)
    combats = sum(r.combats for r in reports)
    failed = [r for r in reports if not r.ok]
    if not failed:
        print(f"SIMULATION OK seeds={args.seeds} turns={turns} combats={combats}")
        return 0
    print(
        f"SIMULATION FAILED seeds={args.seeds} failed={len(failed)} turns={turns} combats={combats}"
    )
    for report in failed:
        for reason in report.failures:
            print("  " + reason.encode("ascii", "replace").decode("ascii").replace("\n", "\n    "))
    return 1


if __name__ == "__main__":
    sys.exit(main())
