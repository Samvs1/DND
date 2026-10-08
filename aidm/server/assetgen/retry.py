"""Retry mode of gen_assets: regenerate only the keys a review marked `retry` (Addendum B.2, B.5).

`plan_retry` reads a `review_<n>.json` (key -> {verdict, prompt_fix, ...}), counts the attempts each
key already has among the staged candidates (one per sidecar that lists the key), and builds the
calls with the normal planner. The review's `prompt_fix` is appended at the end of the prompt, so
the style prefix stays first. A key with MAX_ATTEMPTS attempts is refused with a typed reason and
left for ASSETS_REPORT. Quality is `high` only for a key with two failed medium attempts.
Retries go through the same runner, budget guard and ledger as first attempts.

Public API: `MAX_ATTEMPTS`, `HIGH_AFTER`, `RetryPlan`, `plan_retry`, `staged_history`.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from aidm.server.asset_prompts import StyleBible
from aidm.server.assetgen.costs import PriceTable
from aidm.server.assetgen.plan import PlannedCall, Selection, build_calls, select_keys
from aidm.server.assetgen.priority import PriorityTiers
from aidm.server.assetgen.prompts import RefSources

type Manifest = Mapping[str, Mapping[str, Any]]

MAX_ATTEMPTS = 3
HIGH_AFTER = 2


@dataclass(frozen=True)
class RetryPlan:
    selection: Selection
    calls: list[PlannedCall]


def staged_history(staging: Path) -> dict[str, list[str]]:
    """Per key, the quality of each staged attempt, in sidecar order."""
    history: dict[str, list[str]] = {}
    for sidecar in sorted(staging.glob("*.json")):
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        for key in meta.get("keys", []):
            history.setdefault(key, []).append(str(meta.get("quality", "")))
    return history


def _fixes(review: Path) -> dict[str, str]:
    raw = json.loads(review.read_text(encoding="utf-8"))
    items = raw.get("items", raw) if isinstance(raw, dict) else {}
    return {
        key: str(verdict.get("prompt_fix") or "")
        for key, verdict in items.items()
        if isinstance(verdict, dict) and verdict.get("verdict") == "retry"
    }


def _amend(
    call: PlannedCall, fixes: Mapping[str, str], history: Mapping[str, list[str]]
) -> PlannedCall:
    text = " ".join(dict.fromkeys(fixes[k] for k in call.keys if fixes[k])).strip()
    prompt = f"{call.request.prompt} Fix from review: {text}" if text else call.request.prompt
    failed_medium = max(sum(1 for q in history.get(k, []) if q != "high") for k in call.keys)
    quality = "high" if failed_medium >= HIGH_AFTER else call.request.quality
    return replace(call, request=replace(call.request, prompt=prompt, quality=quality))


def plan_retry(
    review: Path,
    manifest: Manifest,
    static_dir: Path,
    staging: Path,
    tiers: PriorityTiers,
    *,
    bible: StyleBible,
    table: PriceTable,
    refs: RefSources,
) -> RetryPlan:
    """The retry calls for the review's `retry` verdicts, and the keys skipped with a reason."""
    fixes = _fixes(review)
    history = staged_history(staging)
    skipped: list[tuple[str, str]] = []
    allowed: list[str] = []
    for key in fixes:
        if len(history.get(key, [])) >= MAX_ATTEMPTS:
            skipped.append((key, f"max_attempts_reached ({MAX_ATTEMPTS}); left for ASSETS_REPORT"))
        else:
            allowed.append(key)
    chosen = select_keys(manifest, static_dir, tiers, only=allowed)
    skipped += list(chosen.skipped)
    calls = build_calls(manifest, chosen.keys, bible=bible, table=table, refs=refs)
    amended = [_amend(c, fixes, history) for c in calls]
    return RetryPlan(Selection(chosen.keys, tuple(skipped)), amended)
