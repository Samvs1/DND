"""Install reviewed candidates into the asset tree, and revert them (Addendum B.5 step 5).

`install_review` reads `review_<n>.json` (per key: scores subject, style, composition, cleanliness,
readability_64, each 1-5, a verdict accept|retry|reject and an optional prompt_fix) plus the
`review_<n>.index.json` the contact sheet wrote, and installs ONLY keys with verdict accept AND all
five scores >= 4. An install never touches a `real` entry or one whose source is v1, never
overwrites an existing file, re-runs the auto-checks on the final image, writes the PNG and then
the manifest, each atomically (temp file + os.replace), and rolls the PNG back if the manifest
write fails. `revert_asset` removes a generated file and puts the manifest entry back to its
placeholder state; it refuses entries that are not generated.

Public API: `SCORE_NAMES`, `MIN_SCORE`, `LICENSE`, `Outcome`, `InstallRefused`, `RevertRefused`,
`load_manifest`, `score_problem`, `install_review`, `revert_asset`.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aidm.server.assetgen.autocheck import CheckSpec, check_image
from aidm.server.assetgen.candidates import target_size, write_atomic

SCORE_NAMES = ("subject", "style", "composition", "cleanliness", "readability_64")
MIN_SCORE = 4
LICENSE = "AI generated via OpenAI API, check provider terms before commercial use"
GENERATED = "generated:"
BASE_FIELDS = ("kind", "file", "size", "transparent")

type Manifest = dict[str, dict[str, Any]]


class InstallRefused(Exception):
    """An install was refused; `code` says why (typed, never a raw error for players)."""

    def __init__(self, key: str, code: str, detail: str = "") -> None:
        super().__init__(f"{key}: {code} {detail}".strip())
        self.key = key
        self.code = code


class RevertRefused(InstallRefused):
    """A revert was refused (entry unknown, real, v1 or not generated)."""


@dataclass(frozen=True)
class Outcome:
    key: str
    installed: bool
    reason: str


def load_manifest(path: Path) -> Manifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _save_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    write_atomic(path, (json.dumps(manifest, indent=1) + "\n").encode("utf-8"))


def score_problem(review: Mapping[str, Any]) -> str:
    """Empty when the review row qualifies for install, else the reason it does not."""
    if review.get("verdict") != "accept":
        return f"verdict {review.get('verdict')!r} is not accept"
    for name in SCORE_NAMES:
        value = review.get(name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            return f"score {name} missing"
        if value < MIN_SCORE:
            return f"score {name}={value} is below {MIN_SCORE}"
    return ""


def _pick(items: list[dict[str, Any]], key: str, attempt: Any) -> dict[str, Any] | None:
    mine = [i for i in items if i["key"] == key]
    if isinstance(attempt, int):
        mine = [i for i in mine if i["attempt"] == attempt]
    return max(mine, key=lambda i: i["attempt"]) if mine else None


def _guard_target(key: str, entry: Mapping[str, Any], target: Path) -> None:
    source = str(entry.get("source") or "")
    if entry.get("status") == "real" or source == "v1" or source.startswith("manual"):
        raise InstallRefused(key, "real_entry", "real and v1 art is never overwritten")
    if target.exists():
        raise InstallRefused(key, "file_exists", "an existing file is never overwritten")


def _new_entry(entry: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    fresh = {k: entry[k] for k in BASE_FIELDS if k in entry}
    fresh.update(
        status="real",
        prompt=item["prompt"],
        source=f"{GENERATED}{item['model']}",
        license=LICENSE,
        reviewed=True,
        cost_eur=round(float(item["cost_eur"]), 6),
    )
    return fresh


def _install_one(
    key: str, item: Mapping[str, Any], manifest: Manifest, manifest_path: Path, static: Path
) -> None:
    if key not in manifest:
        raise InstallRefused(key, "unknown_key")
    entry = manifest[key]
    target = static / str(entry["file"])
    _guard_target(key, entry, target)
    data = Path(item["image"]).read_bytes()
    spec = CheckSpec(expected_size=target_size(entry), transparent=bool(entry["transparent"]))
    result = check_image(data, spec)
    if not result.ok:
        raise InstallRefused(key, "autocheck", "; ".join(result.reasons))
    write_atomic(target, data)
    previous = manifest[key]
    manifest[key] = _new_entry(entry, item)
    try:
        _save_manifest(manifest_path, manifest)
    except OSError:
        manifest[key] = previous
        target.unlink(missing_ok=True)
        raise


def _try_install(
    key: str,
    row: Mapping[str, Any],
    items: list[dict[str, Any]],
    base: Path,
    manifest: Manifest,
    paths: tuple[Path, Path],
) -> Outcome:
    problem = score_problem(row)
    if problem:
        return Outcome(key, False, problem)
    item = _pick(items, key, row.get("attempt"))
    if item is None:
        return Outcome(key, False, "no candidate image in the review index")
    try:
        _install_one(key, {**item, "image": base / item["image"]}, manifest, *paths)
    except InstallRefused as refused:
        return Outcome(key, False, f"{refused.code}: {refused}")
    return Outcome(key, True, "installed")


def install_review(review_path: Path, manifest_path: Path, static: Path) -> list[Outcome]:
    """Install every qualifying key of a review file; returns one outcome per reviewed key."""
    review = json.loads(review_path.read_text(encoding="utf-8"))
    index_path = review_path.with_name(review_path.stem + ".index.json")
    items: list[dict[str, Any]] = json.loads(index_path.read_text(encoding="utf-8"))["items"]
    manifest = load_manifest(manifest_path)
    paths = (manifest_path, static)
    return [
        _try_install(key, row, items, index_path.parent, manifest, paths)
        for key, row in review.items()
    ]


def revert_asset(key: str, manifest_path: Path, static: Path) -> tuple[str, str]:
    """Back to placeholder; returns the manifest (status, source) text before and after."""
    manifest = load_manifest(manifest_path)
    entry = manifest.get(key)
    if entry is None:
        raise RevertRefused(key, "unknown_key")
    source = str(entry.get("source") or "")
    if not source.startswith(GENERATED) or entry.get("status") != "real":
        raise RevertRefused(key, "not_generated", "only generated assets can be reverted")
    before = f"status={entry['status']} source={source}"
    restored = {k: entry[k] for k in BASE_FIELDS if k in entry}
    restored.update(status="placeholder", prompt=entry.get("prompt", ""), source="", license="")
    manifest[key] = restored
    _save_manifest(manifest_path, manifest)
    (static / str(entry["file"])).unlink(missing_ok=True)
    return before, "status=placeholder source="
