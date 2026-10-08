"""Restore a generated asset to its placeholder state.

Usage: python scripts/revert_asset.py <key>
Removes the installed file, resets the manifest entry, regenerates ASSETS_TODO.md and prints the
manifest status before and after. Refuses v1 and other non-generated entries.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from gen_assets_todo import run as write_todo

from aidm.server.assetgen.review_cli import revert_main

ROOT = Path(__file__).resolve().parent.parent


def _todo() -> None:
    write_todo(ROOT, check=False)


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(revert_main(sys.argv[1:], ROOT, after=_todo))
