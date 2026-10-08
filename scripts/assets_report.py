"""Write ASSETS_REPORT.md (spend, verdict table, counts). `--check` fails when it is stale.

Not part of the gate: the review JSON lives in gitignored artifacts/. No network.
Logic: aidm/server/assetgen/report.py.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from aidm.server.assetgen.report import render_report, write_report

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "aidm" / "web" / "static" / "assets" / "manifest.json"
ART = ROOT / "artifacts" / "assets"
LEDGER = ROOT / "logs" / "asset_spend.json"
OUT = ROOT / "ASSETS_REPORT.md"

if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--check" in sys.argv[1:]:
        fresh = render_report(MANIFEST, ART, LEDGER)
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        print("assets report: ok" if fresh == current else "assets report: STALE")
        raise SystemExit(0 if fresh == current else 1)
    print(write_report(MANIFEST, ART, LEDGER, OUT).relative_to(ROOT).as_posix())
