"""Candidate rows from every `action_declared` event of the committed fixture runs (M36.7).

Usage: python scripts/extract_typed_lines.py [--runs a,b] [--out PATH]
(default out: artifacts/interpret/candidates.jsonl, gitignored)

One JSONL row per typed line: id "<run>:<seq>", run, seq, actor_id, text, scope (the menu's),
menu_ids, router (the old router's reading, serialised, or null) and engine (what the engine did
until the next declared line). These are weak labels for the labeller, not truth.
"""

import argparse
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str]) -> int:
    from scripts.interpret import lib
    from scripts.interpret.extract import candidates

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", default="", help="comma list of run names (default: all)")
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "interpret" / "candidates.jsonl"))
    args = parser.parse_args(argv)
    known = lib.run_names()
    wanted = [r for r in args.runs.split(",") if r] or known
    missing = [r for r in wanted if r not in known]
    if missing:
        print(f"unknown runs: {', '.join(missing)}")
        return 2
    counts = dict.fromkeys(wanted, 0)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in candidates(wanted):
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")
            counts[row["run"]] += 1
    os.replace(tmp, out)
    for run, n in counts.items():
        print(f"{run}: {n}")
    print(f"total: {sum(counts.values())} -> {out}")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
