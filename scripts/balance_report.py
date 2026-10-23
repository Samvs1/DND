"""Balance report: `python scripts/balance_report.py <saves folder or save...> [--json|--markdown]
[--group cell|style|party] [--style NAME]`.

Plain text: one PASS / MISS / N/A line per (style, party, target). `--markdown` prints the same
as a table plus (M29.2) how the runs ended per (style, party), from each run's `tags.json`.
`--group style` pools every party of a style ("all"), `--group party` every style of a party;
`--style` keeps only the runs of one style.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

from aidm.data.balance_targets import load_balance_targets
from aidm.session.balance import evaluate, find_saves, outcomes, run_tags, tags_of
from aidm.session.metrics import compute_metrics, load_defeat_tails, load_events


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:.2f}".rstrip("0").rstrip(".")


def _markdown(rows: list[dict[str, Any]], ends: list[dict[str, Any]]) -> None:
    print("| verdict | style | party | runs | target | value | bounds |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        bounds = f"{_fmt(r['min'])}..{_fmt(r['max'])}"
        cells = [r["verdict"], r["style"], r["party"], str(r["runs"]), r["target"]]
        print("| " + " | ".join([*cells, _fmt(r["value"]), bounds]) + " |")
    print()
    print("| style | party | runs | epilogue | lost for good | top level (median) | wipes/run |")
    print("|---|---|---|---|---|---|---|")
    for e in ends:
        lost = ", ".join(f"{k}: {v}" for k, v in e["lost"].items()) or "-"
        cells = [e["style"], e["party"], str(e["runs"]), str(e["epilogue"]), lost]
        print("| " + " | ".join([*cells, _fmt(e["level"]), _fmt(e["wipes_per_run"])]) + " |")


def _grouped(tags: tuple[str, str], group: str, metrics: Any) -> tuple[str, str, Any]:
    style, party = tags
    if group == "style":
        return style, "all", metrics
    if group == "party":
        return "all", party, metrics
    return style, party, metrics


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--group", choices=("cell", "style", "party"), default="cell")
    ap.add_argument("--style", default=None, help="only the runs of this style")
    args = ap.parse_args()
    saves = [s for p in args.paths if p.exists() for s in find_saves(p)]
    if args.style is not None:
        saves = [s for s in saves if tags_of(s)[0] == args.style]
    entries = [(s, compute_metrics(load_events(s), load_defeat_tails(s))) for s in saves]
    runs = [_grouped(tags_of(s), args.group, m) for s, m in entries]
    rows = evaluate(runs, load_balance_targets())
    if args.json:
        print(json.dumps({"runs": len(runs), "rows": rows}, indent=2))
        return 0
    if args.markdown:
        _markdown(rows, outcomes([(run_tags(s), m) for s, m in entries]))
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
