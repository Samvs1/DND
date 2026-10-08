"""The Scribe's voice build (M13.3, docs/next/GOAL_SCRIBE.md). Logic: aidm/server/voicegen/.

Usage:
  python scripts/gen_scribe_voice.py                    # dry run (default): plan, no network
  python scripts/gen_scribe_voice.py --yes              # Fish TTS for missing raws, then build
  python scripts/gen_scribe_voice.py --reprocess        # rebuild from the raw cache, no API calls
  python scripts/gen_scribe_voice.py --only revive.1    # repeatable; limits the run
  python scripts/gen_scribe_voice.py --check            # offline staleness check of lines.json

Config: data/voice/scribe.json. Raw WAVs: artifacts/voice/raw/. Report and spectrograms:
artifacts/voice/report/. Output: aidm/web/static/audio/voice/scribe/<line_id>.mp3 + lines.json.
Needs FISH_API_KEY in .env for --yes (never printed); VOICE_PROVIDER=fake runs offline.
Exit codes: 0 ok, 1 check problems or bad arguments, 2 raw missing for --reprocess,
3 provider unavailable, 4 a line failed its measurement checks.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from aidm.server.voicegen.cli import main

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:], root=ROOT))
