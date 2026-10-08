"""Command line of scripts/gen_assets.py (Addendum B.4).

Default is a DRY RUN: it prints the entries to generate, the API calls (portraits/banners one call
each, tokens and icons as 4x4 sheets), the worst-case cost of each call, the total and the total
against the cap. It makes no network call and writes nothing. `--yes` (without `--dry-run`) makes
the calls through the provider named by IMAGE_PROVIDER (`openai`, or `fake` for offline runs) under
the budget guard; candidates go to artifacts/assets/candidates/ and are NOT installed.
`--write-priority` / `--check-priority` write or check docs/ASSET_PRIORITY.md.

Exit codes: 0 ok, 1 stale priority doc or bad --only, 2 stopped at the budget cap, 3 provider
unavailable (missing key, no current model, organisation verification needed).

Public API: `main`, `parse_args`, `format_plan`, `RepoPaths`.
"""

import argparse
import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aidm.server.asset_keys import split_key
from aidm.server.asset_prompts import load_style_bible
from aidm.server.assetgen.costs import PriceTable, load_price_table
from aidm.server.assetgen.fake_provider import FakeImageProvider
from aidm.server.assetgen.ledger import BudgetGuard, load_ledger
from aidm.server.assetgen.openai_provider import OpenAIImageProvider
from aidm.server.assetgen.plan import PlannedCall, Selection, build_calls, select_keys
from aidm.server.assetgen.priority import derive_tiers, render_priority
from aidm.server.assetgen.prompts import RefSources
from aidm.server.assetgen.provider import ImageProvider, ProviderError
from aidm.server.assetgen.runner import RunReport, RunSettings, run_calls

type Out = Callable[[str], None]
DEFAULT_CAP_EUR = 8.0
SHOWN_SHEET_KEYS = 4


@dataclass(frozen=True)
class RepoPaths:
    root: Path

    @property
    def static_dir(self) -> Path:
        return self.root / "aidm" / "web" / "static"

    @property
    def manifest(self) -> Path:
        return self.static_dir / "assets" / "manifest.json"

    @property
    def ledger(self) -> Path:
        return self.root / "logs" / "asset_spend.json"

    @property
    def staging(self) -> Path:
        return self.root / "artifacts" / "assets" / "candidates"

    @property
    def priority_doc(self) -> Path:
        return self.root / "docs" / "ASSET_PRIORITY.md"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="gen_assets", description="AI asset generator (Addendum B)")
    p.add_argument("--dry-run", action="store_true", help="plan and price only (the default)")
    p.add_argument("--yes", action="store_true", help="really call the image API")
    p.add_argument("--cap", type=float, default=DEFAULT_CAP_EUR, help="spend cap in EUR")
    p.add_argument("--tier", type=int, choices=(1, 2), default=1, help="2 adds the P2 entries")
    p.add_argument("--only", action="append", default=[], metavar="KEY", help="just this key")
    p.add_argument("--max-attempts", type=int, default=2, help="attempts per call")
    p.add_argument("--v1-root", type=Path, default=None, help="read-only v1 project root")
    p.add_argument("--write-priority", action="store_true", help="write docs/ASSET_PRIORITY.md")
    p.add_argument("--check-priority", action="store_true", help="exit 1 if it is stale")
    return p.parse_args(list(argv))


def _default_v1_root() -> Path:
    return Path(os.environ.get("AIDM_V1_ROOT") or Path.home() / "Desktop" / "DnD")


def _load_manifest(paths: RepoPaths) -> dict[str, dict[str, Any]]:
    raw = json.loads(paths.manifest.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _kind_counts(keys: Sequence[str]) -> str:
    counts: dict[str, int] = {}
    for key in keys:
        counts[split_key(key)[0]] = counts.get(split_key(key)[0], 0) + 1
    return ", ".join(f"{k} {n}" for k, n in sorted(counts.items())) or "none"


def _call_line(n: int, call: PlannedCall, cost: float) -> str:
    req = call.request
    entries = call.keys[0]
    if call.label.startswith("sheet "):
        shown = ", ".join(call.keys[:SHOWN_SHEET_KEYS])
        more = len(call.keys) - SHOWN_SHEET_KEYS
        entries = f"{call.label} ({len(call.keys)}): {shown}" + (
            f", +{more} more" if more > 0 else ""
        )
    refs = len(req.references)
    return (
        f"{n:4d}  {req.endpoint:<8} {refs:<4} {req.size:<10} {req.quality:<7} {cost:.4f}  {entries}"
    )


def format_plan(
    calls: Sequence[PlannedCall], table: PriceTable, *, committed: float, cap: float
) -> list[str]:
    """The priced call list, the total and the total against the cap."""
    singles = sum(1 for c in calls if not c.label.startswith("sheet "))
    lines = [
        "model: chosen from the API model list at run time; estimates use the most expensive row",
        f"API calls: {len(calls)} ({singles} single, {len(calls) - singles} sheets)",
        "   #  endpoint refs size       quality est EUR entries",
    ]
    total = 0.0
    for n, call in enumerate(calls, start=1):
        cost = call.estimate(table, None)
        total += cost
        lines.append(_call_line(n, call, cost))
    projected = committed + total
    verdict = "UNDER CAP" if projected <= cap else "OVER CAP (the run would stop at the cap)"
    lines += [
        f"total worst case: {total:.4f} EUR",
        f"ledger already committed: {committed:.4f} EUR",
        f"projected: {projected:.4f} EUR vs cap {cap:.2f} EUR: {verdict}",
    ]
    return lines


def _priority(paths: RepoPaths, manifest: dict[str, dict[str, Any]], check: bool, out: Out) -> int:
    text = render_priority(derive_tiers(manifest))
    target = paths.priority_doc
    if check:
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        if current == text:
            out("asset priority: ok")
            return 0
        out("asset priority: STALE, run python scripts/gen_assets.py --write-priority")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, target)
    out(f"asset priority: wrote {target.name}")
    return 0


def provider_from_env(root: Path) -> ImageProvider:
    """The provider named by IMAGE_PROVIDER (default openai); values are never echoed."""
    from dotenv import load_dotenv

    load_dotenv(root / ".env", override=False)
    name = (os.environ.get("IMAGE_PROVIDER") or "openai").strip().lower()
    if name == "fake":
        return FakeImageProvider()
    if name != "openai":
        raise ProviderError("IMAGE_PROVIDER must be openai (or fake for offline runs)")
    return OpenAIImageProvider(os.environ.get("IMAGE_API_KEY", ""))


def _report(report: RunReport, guard: BudgetGuard, out: Out) -> int:
    out(f"model: {report.model}")
    out(f"candidates: {len(report.candidates)} images for {len(report.done_keys)} entries")
    if report.failed_keys:
        out(f"failed after retries (stay placeholders): {', '.join(report.failed_keys)}")
    out(f"ledger committed: {guard.committed_eur():.4f} EUR vs cap {guard.cap_eur:.2f} EUR")
    if report.refusal is None:
        return 0
    out(f"STOPPED: {report.refusal}")
    out(f"remaining as placeholders ({len(report.remaining_keys)}):")
    out(", ".join(report.remaining_keys))
    return 2


def _generate(
    args: argparse.Namespace,
    paths: RepoPaths,
    calls: Sequence[PlannedCall],
    provider: ImageProvider | None,
    out: Out,
) -> int:
    try:
        chosen = provider if provider is not None else provider_from_env(paths.root)
        guard = BudgetGuard(paths.ledger, args.cap, lambda: datetime.now(UTC).isoformat())
        settings = RunSettings(paths.staging, max(1, args.max_attempts), out)
        report = run_calls(calls, chosen, guard, load_price_table(), settings)
    except ProviderError as exc:
        out(f"provider unavailable: {exc}")
        return 3
    return _report(report, guard, out)


def _plan(args: argparse.Namespace, paths: RepoPaths, manifest: dict[str, dict[str, Any]]):
    selection: Selection = select_keys(
        manifest, paths.static_dir, derive_tiers(manifest), tier=args.tier, only=args.only
    )
    refs = RefSources(paths.static_dir, args.v1_root or _default_v1_root())
    calls = build_calls(
        manifest, selection.keys, bible=load_style_bible(), table=load_price_table(), refs=refs
    )
    return selection, calls


def main(
    argv: Sequence[str],
    *,
    root: Path,
    provider: ImageProvider | None = None,
    out: Out = print,
) -> int:
    args = parse_args(argv)
    paths = RepoPaths(root)
    manifest = _load_manifest(paths)
    if args.write_priority or args.check_priority:
        return _priority(paths, manifest, args.check_priority, out)
    selection, calls = _plan(args, paths, manifest)
    real = args.yes and not args.dry_run
    out("gen_assets: GENERATE" if real else "gen_assets: DRY RUN - no API call, nothing spent.")
    out(f"tier {args.tier}: {len(selection.keys)} entries ({_kind_counts(selection.keys)})")
    for key, reason in selection.skipped:
        out(f"skipped {key}: {reason}")
    if args.only and not selection.keys:
        return 1
    committed = load_ledger(paths.ledger).committed_eur()
    for line in format_plan(calls, load_price_table(), committed=committed, cap=args.cap):
        out(line)
    if not real:
        out("Add --yes to generate (candidates are staged, not installed).")
        return 0
    return _generate(args, paths, calls, provider, out)
