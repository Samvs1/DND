"""Fetch the 2014 SRD 5.1 JSON files from 5e-bits/5e-database into data/srd/.

Pinned to a commit SHA so downloads are reproducible. Output is re-serialised
deterministically, so running the script twice yields no git diff.
Usage: python scripts/fetch_srd.py [--ref <sha-or-branch>]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = "5e-bits/5e-database"
PINNED_SHA = "a6212beb4b278917c2cff41c2b04c4ef4f3e0d6f"
RAW_URL = "https://raw.githubusercontent.com/{repo}/{ref}/src/2014/en/5e-SRD-{name}.json"
NAMES = [
    "Ability-Scores",
    "Alignments",
    "Backgrounds",
    "Classes",
    "Conditions",
    "Damage-Types",
    "Equipment",
    "Equipment-Categories",
    "Feats",
    "Features",
    "Languages",
    "Levels",
    "Magic-Items",
    "Magic-Schools",
    "Monsters",
    "Proficiencies",
    "Races",
    "Rule-Sections",
    "Rules",
    "Skills",
    "Spells",
    "Subclasses",
    "Subraces",
    "Traits",
    "Weapon-Properties",
]


def out_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "srd"


def download(name: str, ref: str) -> object | None:
    """Return parsed JSON, or None when the file does not exist at this ref."""
    url = RAW_URL.format(repo=REPO, ref=ref, name=name)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def serialise(data: object) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default=PINNED_SHA, help="commit SHA or branch to fetch")
    args = parser.parse_args()
    dest = out_dir()
    dest.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        data = download(name, args.ref)
        if data is None:
            print(f"note: 5e-SRD-{name}.json not found at {args.ref}, skipped")
            continue
        path = dest / f"{name.lower().replace('-', '_')}.json"
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(serialise(data))
        count = len(data) if isinstance(data, list) else 1
        print(f"{path.name}: {count}")
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
