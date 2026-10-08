"""scripts/gen_assets.py (Addendum B.1, B.4, B.6): dry run, real run with the fake, selection."""

import json
from pathlib import Path

import pytest

from aidm.server.assetgen import cli
from aidm.server.assetgen.fake_provider import FakeImageProvider
from aidm.server.assetgen.provider import ImageProvider, ImageRequest, ImageResult, ModelInfo
from aidm.server.assetgen.synthetic_png import png_size
from tests.unit.assetgen.helpers import make_repo, small_manifest


class ExplodingProvider:
    """Any use is a test failure: the dry run must never touch a provider."""

    name = "boom"

    def list_models(self) -> list[ModelInfo]:
        raise AssertionError("network used in a dry run")

    def generate(self, request: ImageRequest, model: str) -> ImageResult:
        raise AssertionError("network used in a dry run")

    def edit(self, request: ImageRequest, model: str) -> ImageResult:
        raise AssertionError("network used in a dry run")


def _run(
    root: Path, argv: list[str], provider: ImageProvider | None = None
) -> tuple[int, list[str]]:
    lines: list[str] = []
    args = [*argv, "--v1-root", str(root / "v1")]
    return cli.main(args, root=root, provider=provider, out=lines.append), lines


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_repo(tmp_path)

    def refuse(_: Path) -> ImageProvider:
        raise AssertionError("provider_from_env called")

    monkeypatch.setattr(cli, "provider_from_env", refuse)
    return tmp_path


def _ledger(root: Path) -> Path:
    return cli.RepoPaths(root).ledger


def test_dry_run_is_the_default_and_spends_nothing(repo: Path) -> None:
    code, lines = _run(repo, [], ExplodingProvider())
    assert code == 0 and lines[0].startswith("gen_assets: DRY RUN")
    assert not _ledger(repo).exists() and not cli.RepoPaths(repo).staging.exists()
    text = "\n".join(lines)
    assert "tier 1: 6 entries" in text and "API calls: 5 (3 single, 2 sheets)" in text
    assert "projected:" in text and "vs cap 8.00 EUR: UNDER CAP" in text


def test_dry_run_leaves_an_existing_ledger_byte_identical(repo: Path) -> None:
    _run(repo, ["--yes"], FakeImageProvider())
    before = _ledger(repo).read_bytes()
    code, lines = _run(repo, ["--dry-run", "--yes"], ExplodingProvider())
    assert code == 0 and _ledger(repo).read_bytes() == before
    assert any(line.startswith("ledger already committed: 0.") for line in lines)


def test_dry_run_reports_over_cap(repo: Path) -> None:
    code, lines = _run(repo, ["--cap", "0.05"], ExplodingProvider())
    assert code == 0 and "OVER CAP" in lines[-2]


def test_yes_generates_staged_candidates_only(repo: Path) -> None:
    provider = FakeImageProvider()
    code, lines = _run(repo, ["--yes"], provider)
    assert code == 0, lines
    staging = cli.RepoPaths(repo).staging
    images = sorted(p.name for p in staging.glob("*.png"))
    assert len(images) == 5 and any(n.startswith("sheet_token__") for n in images)
    sidecar = json.loads(next(staging.glob("sheet_icon__*.json")).read_text(encoding="utf-8"))
    assert sidecar["keys"] == ["item_icon.tool"] and sidecar["sheet"] is True
    assert [c[0] for c in provider.calls] == ["edit"] * 5
    static = cli.RepoPaths(repo).static_dir
    assert not (static / "img" / "portraits" / "race_elf_f.png").exists()
    sheet = next(staging.glob("sheet_token__*.png")).read_bytes()
    assert png_size(sheet) == (64, 64)


def test_tier_two_adds_p2_entries(repo: Path) -> None:
    _, lines = _run(repo, ["--tier", "2"], ExplodingProvider())
    joined = "\n".join(lines)
    assert "tier 2: 9 entries" in joined and "zone_card.cave" in joined
    assert "portrait.npc.werewolf-wolf" in joined and "sfx.hit" not in joined


def test_real_and_v1_entries_are_never_selected(repo: Path) -> None:
    code, lines = _run(repo, ["--only", "portrait.class.wizard", "--yes"], FakeImageProvider())
    assert code == 1 and "skipped portrait.class.wizard: has real or v1 art" in lines
    _, all_lines = _run(repo, ["--tier", "2"], ExplodingProvider())
    assert not any("portrait.class.wizard" in ln or "item_icon.weapon" in ln for ln in all_lines)


def test_existing_files_are_never_overwritten(repo: Path) -> None:
    target = cli.RepoPaths(repo).static_dir / "img" / "portraits" / "race_elf_f.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"hand made")
    code, lines = _run(repo, ["--yes"], FakeImageProvider())
    assert code == 0 and "skipped portrait.race.elf.f: target file already exists" in lines
    assert target.read_bytes() == b"hand made"
    assert not list(cli.RepoPaths(repo).staging.glob("portrait.race.elf.f__*"))


def test_only_limits_the_run_to_the_named_key(repo: Path) -> None:
    provider = FakeImageProvider()
    code, _ = _run(repo, ["--only", "region_banner.tier1", "--yes"], provider)
    assert code == 0 and len(provider.calls) == 1
    assert provider.calls[0][1].size == "1536x1024" and len(provider.calls[0][1].references) == 2


def test_cap_hit_stops_cleanly_and_reports_remaining(repo: Path) -> None:
    code, lines = _run(repo, ["--yes", "--cap", "0.15"], FakeImageProvider())
    assert code == 2
    stop = lines.index(next(line for line in lines if line.startswith("STOPPED:")))
    remaining = lines[stop + 2]
    assert "region_banner.tier1" in remaining or "monster_token.goblin" in remaining
    ledger = json.loads(_ledger(repo).read_text(encoding="utf-8"))
    committed = sum(e["actual_eur"] or e["estimate_eur"] for e in ledger["entries"])
    assert committed <= 0.15


def test_missing_key_is_a_clean_provider_stop(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    monkeypatch.setenv("IMAGE_PROVIDER", "openai")
    monkeypatch.delenv("IMAGE_API_KEY", raising=False)
    code, lines = _run(repo, ["--yes"])
    assert code == 3 and lines[-1] == "provider unavailable: IMAGE_API_KEY is not set"
    assert not _ledger(repo).exists()


def test_priority_doc_check_and_write(repo: Path) -> None:
    assert _run(repo, ["--check-priority"])[0] == 1
    assert _run(repo, ["--write-priority"])[0] == 0
    assert _run(repo, ["--check-priority"])[0] == 0
    doc = cli.RepoPaths(repo).priority_doc.read_text(encoding="utf-8")
    assert "- portrait.npc.werewolf-human" in doc and "werewolf-wolf share its look" in doc
    assert small_manifest()["portrait.class.wizard"]["source"] == "v1"
    assert "portrait.class.wizard" not in doc
