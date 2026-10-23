"""Balance report: `python scripts/balance_report.py <saves folder or save...> [--json]`."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from aidm.data.balance_targets import load_balance_targets
from aidm.session.balance import evaluate, load_runs


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:.2f}".rstrip("0").rstrip(".")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    runs = [r for p in args.paths if p.exists() for r in load_runs(p)]
    rows = evaluate(runs, load_balance_targets())
    if args.json:
        print(json.dumps({"runs": len(runs), "rows": rows}, indent=2))
        return 0
    print(f"runs: {len(runs)}")
    for r in rows:
        bounds = f"[{_fmt(r['min'])}..{_fmt(r['max'])}]"
        who = f"{r['style']}/{r['party']} n={r['runs']}"
        print(f"{r['verdict']:4} {who} {r['target']} = {_fmt(r['value'])} {bounds}")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
