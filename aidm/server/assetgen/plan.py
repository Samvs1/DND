"""Which entries to generate and the API calls that make them (Addendum B.1, B.4).

`select_keys` takes the tier pool (P1, or P1 + P2 with tier 2; or the `--only` keys) and keeps an
entry only when it is a placeholder, not v1, and its target file does not exist: real and v1 art
is never selected and no existing file is ever overwritten. `build_calls` turns the keys into
calls: portraits, banners and zone cards one call each; tokens and icons batched as 4x4 sheets of
up to 16 cells (icons of every icon kind share sheets). Each call carries its worst-case estimate.

Public API: `PlannedCall`, `Selection`, `select_keys`, `build_calls`, `SHEET_GROUPS`.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aidm.server.asset_keys import split_key
from aidm.server.asset_prompts import StyleBible
from aidm.server.assetgen.costs import PriceTable
from aidm.server.assetgen.priority import PriorityTiers, is_eligible
from aidm.server.assetgen.prompts import (
    SINGLE_KINDS,
    RefSources,
    references_for,
    sheet_prompt,
    single_prompt,
    spec_of,
)
from aidm.server.assetgen.provider import ImageRequest

type Manifest = Mapping[str, Mapping[str, Any]]

SHEET_GROUPS = {
    "monster_token": "token",
    "item_icon": "icon",
    "spell_icon": "icon",
    "condition_icon": "icon",
}


@dataclass(frozen=True)
class PlannedCall:
    label: str
    keys: tuple[str, ...]
    request: ImageRequest

    def estimate(self, table: PriceTable, model: str | None) -> float:
        return table.worst_case_eur(
            model=model,
            prompt=self.request.prompt,
            size=self.request.size,
            quality=self.request.quality,
            references=len(self.request.references),
        )


@dataclass(frozen=True)
class Selection:
    keys: tuple[str, ...]
    skipped: tuple[tuple[str, str], ...]


def _why_not(key: str, manifest: Manifest, static_dir: Path) -> str:
    entry = manifest.get(key)
    if entry is None:
        return "not in the manifest"
    if entry.get("status") != "placeholder" or not is_eligible(entry):
        return "has real or v1 art"
    if (static_dir / str(entry["file"])).exists():
        return "target file already exists"
    if split_key(key)[0] not in SINGLE_KINDS and split_key(key)[0] not in SHEET_GROUPS:
        return "kind is not generated"
    return ""


def select_keys(
    manifest: Manifest,
    static_dir: Path,
    tiers: PriorityTiers,
    *,
    tier: int = 1,
    only: Iterable[str] = (),
) -> Selection:
    """The keys to generate, in priority order, and the skipped keys with a reason."""
    wanted = list(dict.fromkeys(only))
    pool = wanted or [*tiers.p1, *(tiers.p2 if tier >= 2 else ())]
    keys: list[str] = []
    skipped: list[tuple[str, str]] = []
    for key in pool:
        reason = _why_not(key, manifest, static_dir)
        if reason:
            skipped.append((key, reason))
        else:
            keys.append(key)
    return Selection(tuple(keys), tuple(skipped))


def _single(
    key: str, entry: Mapping[str, Any], bible: StyleBible, table: PriceTable, refs: RefSources
) -> PlannedCall:
    spec = spec_of(key, entry)
    references = references_for(spec.kind, refs)
    prompt = single_prompt(bible, spec, with_refs=bool(references))
    request = ImageRequest(
        prompt, table.size_for(spec.kind), table.default_quality, spec.transparent, references
    )
    return PlannedCall(key, (key,), request)


def _sheets(
    group: str,
    keys: Sequence[str],
    manifest: Manifest,
    bible: StyleBible,
    table: PriceTable,
    refs: RefSources,
) -> list[PlannedCall]:
    references = references_for(f"sheet:{group}", refs)[:1]
    chunks = [keys[i : i + table.sheet_cells] for i in range(0, len(keys), table.sheet_cells)]
    calls: list[PlannedCall] = []
    for n, chunk in enumerate(chunks, start=1):
        specs = [spec_of(k, manifest[k]) for k in chunk]
        prompt = sheet_prompt(bible, specs, with_ref=bool(references), cells=table.sheet_cells)
        transparent = any(s.transparent for s in specs)
        request = ImageRequest(
            prompt, table.sheet_size, table.default_quality, transparent, references
        )
        calls.append(PlannedCall(f"sheet {group} {n}/{len(chunks)}", tuple(chunk), request))
    return calls


def build_calls(
    manifest: Manifest,
    keys: Sequence[str],
    *,
    bible: StyleBible,
    table: PriceTable,
    refs: RefSources,
) -> list[PlannedCall]:
    """Single calls first (in key order), then the sheets of each group."""
    calls: list[PlannedCall] = []
    grouped: dict[str, list[str]] = {}
    for key in keys:
        kind = split_key(key)[0]
        if kind in SHEET_GROUPS:
            grouped.setdefault(SHEET_GROUPS[kind], []).append(key)
        else:
            calls.append(_single(key, manifest[key], bible, table, refs))
    for group in sorted(grouped):
        calls += _sheets(group, grouped[group], manifest, bible, table, refs)
    return calls
