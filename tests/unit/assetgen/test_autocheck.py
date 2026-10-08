"""Auto-checks (Addendum B.5 step 1): every failure class, and the runner retry hook."""

from pathlib import Path

from aidm.server.asset_prompts import load_style_bible
from aidm.server.assetgen.autocheck import MAX_BYTES, CheckSpec, check_image, reasons_for_request
from aidm.server.assetgen.costs import load_price_table
from aidm.server.assetgen.fake_provider import FakeImageProvider
from aidm.server.assetgen.ledger import BudgetGuard, load_ledger
from aidm.server.assetgen.plan import build_calls
from aidm.server.assetgen.prompts import RefSources
from aidm.server.assetgen.provider import ImageRequest
from aidm.server.assetgen.runner import RunSettings, run_calls
from tests.unit.assetgen.helpers import make_repo, small_manifest
from tests.unit.assetgen.imgs import bordered_png, flat_png, noise_png


def test_good_image_passes() -> None:
    assert check_image(noise_png(64, 64), CheckSpec(expected_size=(64, 64))).ok


def test_blank_image_fails() -> None:
    result = check_image(flat_png(64, 64, (90, 90, 90, 255)), CheckSpec())
    assert not result.ok and any("blank" in r for r in result.reasons)


def test_wrong_size_fails() -> None:
    result = check_image(noise_png(64, 64), CheckSpec(expected_size=(128, 128)))
    assert not result.ok and any("wrong size" in r for r in result.reasons)


def test_wrong_ratio_fails() -> None:
    result = check_image(noise_png(64, 64), CheckSpec(expected_ratio=2.0))
    assert not result.ok and any("aspect" in r for r in result.reasons)


def test_missing_alpha_fails_when_transparency_is_required() -> None:
    result = check_image(noise_png(64, 64), CheckSpec(transparent=True))
    assert not result.ok and any("alpha" in r for r in result.reasons)


def test_opaque_corners_fail_when_transparency_is_required() -> None:
    data = noise_png(64, 64, alpha=True)
    assert check_image(data, CheckSpec(transparent=True)).ok
    import io

    from PIL import Image

    image = Image.open(io.BytesIO(data)).convert("RGBA")
    image.putpixel((0, 0), (255, 0, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    result = check_image(buffer.getvalue(), CheckSpec(transparent=True))
    assert not result.ok and any("corner" in r for r in result.reasons)


def test_uniform_border_fails() -> None:
    result = check_image(bordered_png(80, 80), CheckSpec())
    assert not result.ok and any("border" in r for r in result.reasons)


def test_huge_and_garbage_files_fail() -> None:
    assert not check_image(b"x" * (MAX_BYTES + 1), CheckSpec()).ok
    assert any("readable" in r for r in check_image(b"not a png at all" * 20, CheckSpec()).reasons)


def test_request_hook_checks_the_aspect_ratio_of_the_request() -> None:
    assert reasons_for_request("1536x1024", False, noise_png(96, 64)) == []
    assert reasons_for_request("1536x1024", False, noise_png(64, 64))


def test_failed_autocheck_is_retried_and_still_counts_in_the_ledger(tmp_path: Path) -> None:
    v1 = make_repo(tmp_path)
    table = load_price_table()
    refs = RefSources(tmp_path / "aidm" / "web" / "static", v1)
    calls = build_calls(
        small_manifest(), ["portrait.race.elf.f"], bible=load_style_bible(), table=table, refs=refs
    )
    seen: list[int] = []

    def check(_: ImageRequest, __: bytes) -> list[str]:
        seen.append(1)
        return ["blank"] if len(seen) == 1 else []

    guard = BudgetGuard(tmp_path / "logs" / "asset_spend.json", 8.0)
    settings = RunSettings(tmp_path / "staging", 2, check=check)
    report = run_calls(calls, FakeImageProvider(), guard, table, settings)
    assert report.done_keys == ["portrait.race.elf.f"] and len(report.candidates) == 1
    entries = load_ledger(guard.path).entries
    assert [e.attempt for e in entries] == [1, 2]
    assert all(e.status == "settled" for e in entries)


def test_every_attempt_failing_the_autocheck_leaves_the_key_failed(tmp_path: Path) -> None:
    v1 = make_repo(tmp_path)
    table = load_price_table()
    refs = RefSources(tmp_path / "aidm" / "web" / "static", v1)
    calls = build_calls(
        small_manifest(), ["portrait.race.elf.f"], bible=load_style_bible(), table=table, refs=refs
    )
    guard = BudgetGuard(tmp_path / "logs" / "asset_spend.json", 8.0)
    settings = RunSettings(tmp_path / "staging", 2, check=lambda _r, _d: ["blank"])
    report = run_calls(calls, FakeImageProvider(), guard, table, settings)
    assert report.failed_keys == ["portrait.race.elf.f"] and not report.candidates
    assert len(load_ledger(guard.path).entries) == 2
