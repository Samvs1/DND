"""The dice sounds (M26.8, docs/next/GOAL_DICE.md). Logic: aidm/server/sfxgen/.

Usage:
  python scripts/gen_dice_sfx.py           # synthesise every sound (one mp3 encode each), timing
  python scripts/gen_dice_sfx.py --check   # offline: every file is there and the timing is fresh

Output: aidm/web/static/audio/sfx/<name>.mp3 and aidm/web/static/audio/sfx/dice_timing.json.
Exit codes: 0 ok, 1 check problems.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from aidm.server.sfxgen.cli import main

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:], root=ROOT))
