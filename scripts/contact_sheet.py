"""Render artifacts/assets/review_<n>.png: <= 12 labelled candidates plus 2 v1 references.

Usage: python scripts/contact_sheet.py [--offset N] [--limit 12]
Also writes review_<n>.index.json, which scripts/install_assets.py needs.
Logic: aidm/server/assetgen/review_cli.py.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from aidm.server.assetgen.review_cli import contact_sheet_main

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(contact_sheet_main(sys.argv[1:], ROOT))
