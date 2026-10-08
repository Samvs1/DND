"""Command lines of the review pipeline (Addendum B.5): contact sheets, install, revert.

- `contact_sheet_main`: slices/fits the staged candidates, renders `artifacts/assets/review_<n>.png`
  (<= 12 candidates, 2 v1 reference thumbnails on top, a 64 px rendition beside each) and writes
  `review_<n>.index.json`, the list of (key, attempt, image, model, prompt, cost) the sheet shows.
- `install_main`: installs the accepted keys of `review_<n>.json` (see install.py) and calls
  the `after` hook (ASSETS_TODO regeneration, wired by the script).
- `revert_main`: restores one generated key to its placeholder and prints the manifest status
  before and after.

Exit codes: 0 ok, 1 refused or nothing to do.

Public API: `contact_sheet_main`, `install_main`, `revert_main`.
"""

import argparse
import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path

from aidm.server.assetgen.candidates import Candidate, collect, write_atomic
from aidm.server.assetgen.contactsheet import (
    MAX_CANDIDATES,
    MAX_REFERENCES,
    LabelledImage,
    render_contact_sheet,
)
from aidm.server.assetgen.install import (
    InstallRefused,
    install_review,
    load_manifest,
    revert_asset,
)
from aidm.server.assetgen.prompts import PORTRAIT_REFS

type Hook = Callable[[], None]
type Out = Callable[[str], None]


class Paths:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.static = root / "aidm" / "web" / "static"
        self.manifest = self.static / "assets" / "manifest.json"
        self.base = root / "artifacts" / "assets"
        self.staging = self.base / "candidates"
        self.slices = self.base / "slices"


def _next_number(base: Path) -> int:
    numbers = [
        int(m.group(1))
        for p in base.glob("review_*.png")
        if (m := re.match(r"review_(\d+)$", p.stem))
    ]
    return max(numbers, default=0) + 1


def _references(static: Path) -> list[LabelledImage]:
    found = [static / rel for rel in PORTRAIT_REFS if (static / rel).is_file()]
    return [LabelledImage(f"v1 ref {p.stem}", p.read_bytes()) for p in found[:MAX_REFERENCES]]


def _index_item(c: Candidate, base: Path) -> dict[str, object]:
    return {
        "key": c.key,
        "attempt": c.attempt,
        "image": c.image.relative_to(base).as_posix(),
        "model": c.model,
        "prompt": c.prompt,
        "cost_eur": c.cost_eur,
        "note": c.note,
    }


def contact_sheet_main(argv: Sequence[str], root: Path, out: Out = print) -> int:
    parser = argparse.ArgumentParser(prog="contact_sheet")
    parser.add_argument("--offset", type=int, default=0, help="skip this many candidates")
    parser.add_argument("--limit", type=int, default=MAX_CANDIDATES, help="at most 12")
    args = parser.parse_args(list(argv))
    paths = Paths(root)
    manifest = load_manifest(paths.manifest)
    pending = [
        c
        for c in collect(paths.staging, paths.slices, manifest)
        if manifest[c.key].get("status") != "real"
    ]
    window = pending[max(0, args.offset) :][: max(1, min(args.limit, MAX_CANDIDATES))]
    if not window:
        out("contact sheet: no candidates to review")
        return 1
    number = _next_number(paths.base)
    labelled = [
        LabelledImage(f"{c.key} (attempt {c.attempt})", c.image.read_bytes()) for c in window
    ]
    png = render_contact_sheet(
        labelled, _references(paths.static), f"review {number}", paths.base / f"review_{number}.png"
    )
    index = json.dumps({"items": [_index_item(c, paths.base) for c in window]}, indent=1) + "\n"
    write_atomic(paths.base / f"review_{number}.index.json", index.encode("utf-8"))
    out(f"contact sheet: wrote {png.name} with {len(window)} candidates")
    return 0


def install_main(
    argv: Sequence[str], root: Path, after: Hook | None = None, out: Out = print
) -> int:
    parser = argparse.ArgumentParser(prog="install_assets")
    parser.add_argument("review", type=Path, help="artifacts/assets/review_<n>.json")
    args = parser.parse_args(list(argv))
    paths = Paths(root)
    outcomes = install_review(args.review, paths.manifest, paths.static)
    for item in outcomes:
        out(f"{'installed' if item.installed else 'skipped'}: {item.key} ({item.reason})")
    if any(o.installed for o in outcomes) and after is not None:
        after()
    return 0 if outcomes and all(o.installed for o in outcomes) else 1


def revert_main(
    argv: Sequence[str], root: Path, after: Hook | None = None, out: Out = print
) -> int:
    parser = argparse.ArgumentParser(prog="revert_asset")
    parser.add_argument("key")
    args = parser.parse_args(list(argv))
    paths = Paths(root)
    try:
        before, now = revert_asset(args.key, paths.manifest, paths.static)
    except InstallRefused as refused:
        out(f"revert refused: {refused}")
        return 1
    out(f"{args.key} before: {before}")
    out(f"{args.key} after:  {now}")
    if after is not None:
        after()
    return 0
