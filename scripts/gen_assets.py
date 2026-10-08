"""AI asset generator (docs/ADDENDUM_ASSET_GEN.md, Addendum B). Logic: aidm/server/assetgen/.

Usage:
  python scripts/gen_assets.py                      # dry run (default): entries, calls, cost, cap
  python scripts/gen_assets.py --yes --cap 8        # generate candidates under the budget guard
  python scripts/gen_assets.py --tier 2             # include P2 entries
  python scripts/gen_assets.py --only portrait.race.elf.f
  python scripts/gen_assets.py --write-priority     # write docs/ASSET_PRIORITY.md
  python scripts/gen_assets.py --check-priority     # exit 1 when it is stale

Real generation needs IMAGE_PROVIDER=openai and IMAGE_API_KEY in .env; the key is never printed.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from aidm.server.assetgen.cli import main

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:], root=ROOT))
