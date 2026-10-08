"""Run planned calls through an image provider under the budget guard (Addendum B.4).

The model is chosen from the provider's model list (`select_model`) unless given. Each attempt of
each call is booked in the ledger before the request at the worst case for that model and settled
after with the actual cost; a provider error marks the attempt failed (it still counts) and the
call is retried up to `max_attempts`. A `BudgetRefused` stops the run cleanly: the refused call and
every later one are reported as remaining (they stay placeholders). Results are candidates only:
each image and a JSON sidecar (keys, cell order, model, prompt, cost) go to the staging directory,
atomically and never over an existing file. Installing is a separate, reviewed step.

Public API: `RunSettings`, `RunReport`, `run_calls`, `write_candidate`.
"""

import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from aidm.server.assetgen.costs import PriceTable
from aidm.server.assetgen.ledger import BudgetGuard, BudgetRefused
from aidm.server.assetgen.plan import PlannedCall
from aidm.server.assetgen.provider import (
    ImageProvider,
    ImageRequest,
    ImageResult,
    ProviderError,
    select_model,
)


def _quiet(_: str) -> None:
    return None


@dataclass(frozen=True)
class RunSettings:
    staging_dir: Path
    max_attempts: int = 2
    log: Callable[[str], None] = _quiet


@dataclass
class RunReport:
    model: str
    candidates: list[Path] = field(default_factory=list)
    done_keys: list[str] = field(default_factory=list)
    failed_keys: list[str] = field(default_factory=list)
    remaining_keys: list[str] = field(default_factory=list)
    refusal: BudgetRefused | None = None


def _fresh(path: Path) -> Path:
    n = 1
    candidate = path
    while candidate.exists():
        n += 1
        candidate = path.with_name(f"{path.stem}_{n}{path.suffix}")
    return candidate


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_candidate(
    staging_dir: Path, call: PlannedCall, result: ImageResult, call_id: str, cost_eur: float
) -> Path:
    """Save one candidate image plus its JSON sidecar; returns the image path."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    sheet = call.label.startswith("sheet ")
    stem = f"sheet_{call.label.split()[1]}" if sheet else call.keys[0]
    image_path = _fresh(staging_dir / f"{stem}__{call_id}.png")
    meta = {
        "keys": list(call.keys),
        "sheet": sheet,
        "call_id": call_id,
        "model": result.model,
        "endpoint": call.request.endpoint,
        "size": call.request.size,
        "quality": call.request.quality,
        "references": [p.name for p in call.request.references],
        "prompt": call.request.prompt,
        "cost_eur": cost_eur,
    }
    _atomic_write(image_path, result.image)
    _atomic_write(image_path.with_suffix(".json"), (json.dumps(meta, indent=1) + "\n").encode())
    return image_path


def _invoke(provider: ImageProvider, request: ImageRequest, model: str) -> ImageResult:
    if request.references:
        return provider.edit(request, model)
    return provider.generate(request, model)


def _run_one(
    call: PlannedCall,
    provider: ImageProvider,
    guard: BudgetGuard,
    table: PriceTable,
    settings: RunSettings,
    model: str,
) -> Path | None:
    estimate = call.estimate(table, model)
    for attempt in range(1, settings.max_attempts + 1):
        call_id = guard.reserve(
            keys=list(call.keys),
            model=model,
            endpoint=call.request.endpoint,
            size=call.request.size,
            quality=call.request.quality,
            attempt=attempt,
            estimate_eur=estimate,
        )
        try:
            result = _invoke(provider, call.request, model)
        except ProviderError as exc:
            guard.fail(call_id)
            settings.log(f"{call.label}: attempt {attempt} failed: {exc}")
            continue
        cost = table.actual_eur(model, result.usage)
        guard.settle(call_id, cost)
        path = write_candidate(
            settings.staging_dir, call, result, call_id, cost if cost is not None else estimate
        )
        settings.log(f"{call.label}: candidate {path.name}")
        return path
    return None


def run_calls(
    calls: Sequence[PlannedCall],
    provider: ImageProvider,
    guard: BudgetGuard,
    table: PriceTable,
    settings: RunSettings,
    *,
    model: str | None = None,
) -> RunReport:
    """Make every call in order until done or refused by the budget guard."""
    report = RunReport(model=model or select_model(provider.list_models(), table.retired_models))
    for index, call in enumerate(calls):
        try:
            path = _run_one(call, provider, guard, table, settings, report.model)
        except BudgetRefused as refused:
            report.refusal = refused
            report.remaining_keys = [k for c in calls[index:] for k in c.keys]
            settings.log(f"stopped: {refused}")
            break
        if path is None:
            report.failed_keys += call.keys
        else:
            report.candidates.append(path)
            report.done_keys += call.keys
    return report
