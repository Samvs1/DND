"""Rewrite the generated tables of docs/PLAYER_MANUAL.md from the game data (M14.1).

Usage: python scripts/gen_manual.py          rewrite the sections between the markers
       python scripts/gen_manual.py --check  exit 1 with one ASCII line per stale section
"""

import io
import sys

from aidm.data.manual_gen import MANUAL_PATH, splice, stale_sections


def main(argv: list[str]) -> int:
    text = MANUAL_PATH.read_text(encoding="utf-8")
    if "--check" in argv:
        stale = stale_sections(text)
        for name in stale:
            print(f"manual: section '{name}' is stale, run python scripts/gen_manual.py")
        if not stale:
            print("manual: ok")
        return 1 if stale else 0
    new = splice(text)
    if new != text:
        tmp = MANUAL_PATH.with_suffix(".md.tmp")
        tmp.write_text(new, encoding="utf-8", newline="\n")
        tmp.replace(MANUAL_PATH)
    print("manual: written" if new != text else "manual: unchanged")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
