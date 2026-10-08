"""Install the accepted keys of artifacts/assets/review_<n>.json (all five scores >= 4).

Usage: python scripts/install_assets.py artifacts/assets/review_1.json
Updates the manifest and regenerates ASSETS_TODO.md. Never overwrites real or v1 art.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from gen_assets_todo import run as write_todo

from aidm.server.assetgen.review_cli import install_main

ROOT = Path(__file__).resolve().parent.parent


def _todo() -> None:
    write_todo(ROOT, check=False)


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(install_main(sys.argv[1:], ROOT, after=_todo))
