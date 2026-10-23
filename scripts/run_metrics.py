"""Metrics from one save: `python scripts/run_metrics.py <save dir or events.jsonl> [--json]`."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from aidm.session.metrics import compute_metrics, load_defeat_tails, load_events


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("save", type=Path)
    ap.add_argument("--json", action="store_true", help="compact one-line JSON")
    args = ap.parse_args()
    path: Path = args.save
    if not path.exists():
        print(f"no such save: {path}")
        return 2
    metrics = compute_metrics(load_events(path), load_defeat_tails(path))
    print(
        json.dumps(metrics, sort_keys=True)
        if args.json
        else json.dumps(metrics, indent=2, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
