"""Budget guard and ledger (Addendum B.4, B.6): before/after booking, cap refusal, retries count."""

import json
from pathlib import Path

import pytest

from aidm.server.asset_prompts import load_style_bible
from aidm.server.assetgen.costs import load_price_table
from aidm.server.assetgen.fake_provider import FakeImageProvider
from aidm.server.assetgen.ledger import BudgetGuard, BudgetRefused, load_ledger
from aidm.server.assetgen.plan import PlannedCall, build_calls
from aidm.server.assetgen.prompts import RefSources
from aidm.server.assetgen.provider import ImageRequest, ImageUsage
from aidm.server.assetgen.runner import RunSettings, run_calls
from tests.unit.assetgen.helpers import make_repo, small_manifest

TABLE = load_price_table()
MODEL = "gpt-image-1.5"


def _calls(tmp_path: Path, keys: list[str]) -> list[PlannedCall]:
    v1 = make_repo(tmp_path)
    refs = RefSources(tmp_path / "aidm" / "web" / "static", v1)
    return build_calls(small_manifest(), keys, bible=load_style_bible(), table=TABLE, refs=refs)


def _guard(tmp_path: Path, cap: float) -> BudgetGuard:
    return BudgetGuard(tmp_path / "logs" / "asset_spend.json", cap)


def _settings(tmp_path: Path, attempts: int = 2) -> RunSettings:
    return RunSettings(tmp_path / "staging", attempts)


def test_ledger_is_written_before_the_call_and_updated_after(tmp_path: Path) -> None:
    calls = _calls(tmp_path, ["portrait.race.elf.f"])
    guard = _guard(tmp_path, 8.0)
    seen: list[dict[str, object]] = []

    def inspect(_: ImageRequest) -> None:
        entry = load_ledger(guard.path).entries[-1]
        seen.append(entry.model_dump())

    provider = FakeImageProvider(on_call=inspect)
    report = run_calls(calls, provider, guard, TABLE, _settings(tmp_path))
    estimate = calls[0].estimate(TABLE, MODEL)
    assert report.model == MODEL and report.done_keys == ["portrait.race.elf.f"]
    assert seen[0]["status"] == "reserved" and seen[0]["actual_eur"] is None
    assert seen[0]["estimate_eur"] == estimate and seen[0]["keys"] == ["portrait.race.elf.f"]
    after = load_ledger(guard.path).entries
    assert len(after) == 1 and after[0].status == "settled" and after[0].usage_reported
    usage = ImageUsage(300, 1500, 1056, reported=True)  # fake usage with 3 references
    assert after[0].actual_eur == TABLE.actual_eur(MODEL, usage)
    assert after[0].actual_eur is not None and after[0].actual_eur < estimate
    assert load_ledger(guard.path).committed_eur() == after[0].actual_eur


def test_call_past_the_cap_is_refused_with_a_typed_refusal(tmp_path: Path) -> None:
    calls = _calls(tmp_path, ["portrait.race.elf.f", "region_banner.tier1"])
    guard = _guard(tmp_path, 0.01)
    provider = FakeImageProvider()
    report = run_calls(calls, provider, guard, TABLE, _settings(tmp_path))
    assert isinstance(report.refusal, BudgetRefused)
    assert report.refusal.cap_eur == 0.01 and report.refusal.committed_eur == 0.0
    assert report.remaining_keys == ["portrait.race.elf.f", "region_banner.tier1"]
    assert provider.calls == [] and not guard.path.exists()


def test_reserve_refuses_without_writing_anything(tmp_path: Path) -> None:
    guard = _guard(tmp_path, 0.10)
    args = {"model": MODEL, "endpoint": "edit", "size": "1024x1024", "quality": "medium"}
    guard.reserve(keys=["a"], attempt=1, estimate_eur=0.06, **args)
    before = guard.path.read_bytes()
    with pytest.raises(BudgetRefused):
        guard.reserve(keys=["b"], attempt=1, estimate_eur=0.05, **args)
    assert guard.path.read_bytes() == before
    assert not list(guard.path.parent.glob("*.tmp"))


def test_retries_count_toward_the_cap(tmp_path: Path) -> None:
    calls = _calls(tmp_path, ["portrait.race.elf.f"])
    estimate = calls[0].estimate(TABLE, MODEL)
    guard = _guard(tmp_path, estimate * 1.5)
    provider = FakeImageProvider(fail_on={1})
    report = run_calls(calls, provider, guard, TABLE, _settings(tmp_path, attempts=3))
    entries = load_ledger(guard.path).entries
    assert [e.status for e in entries] == ["failed"]
    assert entries[0].actual_eur is None and guard.committed_eur() == estimate
    assert isinstance(report.refusal, BudgetRefused) and len(provider.calls) == 1
    assert report.remaining_keys == ["portrait.race.elf.f"] and report.candidates == []


def test_a_failed_attempt_then_a_success_books_both(tmp_path: Path) -> None:
    calls = _calls(tmp_path, ["portrait.race.elf.f"])
    guard = _guard(tmp_path, 8.0)
    report = run_calls(
        calls, FakeImageProvider(fail_on={1}), guard, TABLE, _settings(tmp_path, attempts=2)
    )
    entries = load_ledger(guard.path).entries
    assert [(e.status, e.attempt) for e in entries] == [("failed", 1), ("settled", 2)]
    assert guard.committed_eur() == pytest.approx(entries[0].estimate_eur + entries[1].committed())
    assert report.done_keys == ["portrait.race.elf.f"] and len(report.candidates) == 1


def test_all_attempts_failing_leaves_the_entry_a_placeholder(tmp_path: Path) -> None:
    calls = _calls(tmp_path, ["portrait.race.elf.f", "region_banner.tier1"])
    guard = _guard(tmp_path, 8.0)
    provider = FakeImageProvider(fail_on={1, 2})
    report = run_calls(calls, provider, guard, TABLE, _settings(tmp_path, attempts=2))
    assert report.failed_keys == ["portrait.race.elf.f"]
    assert report.done_keys == ["region_banner.tier1"] and report.refusal is None


def test_missing_usage_keeps_the_worst_case_committed(tmp_path: Path) -> None:
    calls = _calls(tmp_path, ["portrait.race.elf.f"])
    guard = _guard(tmp_path, 8.0)
    provider = FakeImageProvider(usage=ImageUsage())
    run_calls(calls, provider, guard, TABLE, _settings(tmp_path))
    entry = load_ledger(guard.path).entries[0]
    assert entry.status == "settled" and not entry.usage_reported
    assert guard.committed_eur() == calls[0].estimate(TABLE, MODEL)


def test_ledger_is_cumulative_across_runs(tmp_path: Path) -> None:
    calls = _calls(tmp_path, ["portrait.race.elf.f"])
    guard = _guard(tmp_path, 8.0)
    run_calls(calls, FakeImageProvider(), guard, TABLE, _settings(tmp_path))
    first = guard.committed_eur()
    run_calls(calls, FakeImageProvider(), guard, TABLE, _settings(tmp_path))
    assert guard.committed_eur() == pytest.approx(2 * first)
    raw = json.loads(guard.path.read_text(encoding="utf-8"))
    assert [e["call_id"] for e in raw["entries"]] == ["c00001", "c00002"]
