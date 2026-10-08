"""Write artifacts/assets/FINAL_REVIEW.png and FINAL_REVIEW_<n>.png for the final human review.

Usage: python scripts/final_review.py
Logic: aidm/server/assetgen/final_review.py. No network.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from aidm.server.assetgen.final_review import build_final_review

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "aidm" / "web" / "static"

if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    for path in build_final_review(
        STATIC / "assets" / "manifest.json", STATIC, ROOT / "artifacts" / "assets"
    ):
        print(path.relative_to(ROOT).as_posix())
