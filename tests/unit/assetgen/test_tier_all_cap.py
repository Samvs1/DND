"""M12.1: `--tier all` (P1 + P2, never real or v1), priority order and the cap cut, UI art keys."""

import json
from pathlib import Path
from typing import Any

import pytest

from aidm.server.asset_keys import derive_specs
from aidm.server.asset_prompts import load_style_bible
from aidm.server.asset_ui import UI_ART
from aidm.server.assetgen import cli
from aidm.server.assetgen.costs import load_price_table
from aidm.server.assetgen.fake_provider import FakeImageProvider
from aidm.server.assetgen.plan import build_calls, fit_to_cap, select_keys
from aidm.server.assetgen.priority import derive_tiers
from aidm.server.assetgen.prompts import RefSources
from aidm.server.assetgen.provider import ImageProvider
from tests.unit.assetgen.helpers import REPO_ROOT, make_repo, small_manifest

TABLE = load_price_table()
STATIC = REPO_ROOT / "aidm" / "web" / "static"


def _guarded_manifest() -> dict[str, dict[str, Any]]:
    """The small manifest plus entries `--tier all` must never touch."""
    manifest = small_manifest()
    blinded = {**manifest["condition_icon.asleep"], "file": "img/icons/conditions/blinded.png"}
    manifest["condition_icon.blinded"] = {**blinded, "source": "v1"}  # v1 key, file missing
    forest = {**manifest["zone_card.cave"], "file": "img/zones/forest.png"}
    manifest["zone_card.forest"] = {**forest, "status": "real", "source": "generated:m"}
    return manifest


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_repo(tmp_path, _guarded_manifest())

    def refuse(_: Path) -> ImageProvider:
        raise AssertionError("provider_from_env called")

    monkeypatch.setattr(cli, "provider_from_env", refuse)
    return tmp_path


def _run(root: Path, argv: list[str], provider: ImageProvider) -> tuple[int, list[str]]:
    lines: list[str] = []
    args = [*argv, "--v1-root", str(root / "v1")]
    return cli.main(args, root=root, provider=provider, out=lines.append), lines


def _staged_keys(root: Path) -> set[str]:
    staging = cli.RepoPaths(root).staging
    return {k for p in staging.glob("*.json") for k in json.loads(p.read_text("utf-8"))["keys"]}


def test_tier_all_generates_p1_and_p2_but_never_real_v1_or_existing(repo: Path) -> None:
    hand = cli.RepoPaths(repo).static_dir / "img" / "monsters" / "bandit.png"
    hand.parent.mkdir(parents=True, exist_ok=True)
    hand.write_bytes(b"hand made")
    code, lines = _run(repo, ["--tier", "all", "--yes", "--cap", "15"], FakeImageProvider())
    assert code == 0, lines
    assert any(line.startswith("tier all: 8 entries") for line in lines)
    assert "skipped monster_token.bandit: target file already exists" in lines
    staged = _staged_keys(repo)
    assert {"portrait.npc.werewolf-wolf", "zone_card.cave", "monster_token.goblin"} <= staged
    never = {"portrait.class.wizard", "item_icon.weapon", "condition_icon.blinded"}
    assert not staged & (never | {"zone_card.forest", "monster_token.bandit", "sfx.hit"})
    assert hand.read_bytes() == b"hand made"


def test_calls_follow_priority_p1_before_p2() -> None:
    manifest = small_manifest()
    tiers = derive_tiers(manifest)
    keys = select_keys(manifest, Path("missing-static"), tiers, tier=2).keys
    calls = build_calls(
        manifest, keys, bible=load_style_bible(), table=TABLE, refs=RefSources(Path("none"))
    )
    rank = {k: n for n, k in enumerate(keys)}
    firsts = [min(rank[k] for k in c.keys) for c in calls]
    assert firsts == sorted(firsts)
    with_p1 = [n for n, c in enumerate(calls) if any(k in tiers.p1 for k in c.keys)]
    p2_only = [n for n, c in enumerate(calls) if all(k not in tiers.p1 for k in c.keys)]
    assert with_p1 and p2_only and max(with_p1) < min(p2_only)


def test_over_cap_plan_is_cut_from_the_end_and_only_kept_calls_run(repo: Path) -> None:
    manifest = _guarded_manifest()
    keys = select_keys(manifest, Path("missing"), derive_tiers(manifest), tier=2).keys
    refs = RefSources(cli.RepoPaths(repo).static_dir, repo / "v1")
    calls = build_calls(manifest, keys, bible=load_style_bible(), table=TABLE, refs=refs)
    cap = sum(c.estimate(TABLE, None) for c in calls[:2]) + 0.0001
    kept, cut = fit_to_cap(calls, TABLE, committed=0.0, cap=cap)
    assert kept == calls[:2] and cut == calls[2:]
    provider = FakeImageProvider()
    code, lines = _run(repo, ["--tier", "all", "--yes", "--cap", f"{cap:.4f}"], provider)
    assert code == 0, lines
    cut_line = lines[lines.index(next(ln for ln in lines if ln.startswith("cut by cap ("))) + 1]
    assert all(k in cut_line for c in cut for k in c.keys)
    assert len(provider.calls) == 2
    ledger = json.loads(cli.RepoPaths(repo).ledger.read_text(encoding="utf-8"))
    assert sum(e["actual_eur"] or e["estimate_eur"] for e in ledger["entries"]) <= cap


def test_a_plan_with_nothing_under_the_cap_is_refused(repo: Path) -> None:
    provider = FakeImageProvider()
    code, lines = _run(repo, ["--tier", "all", "--yes", "--cap", "0.001"], provider)
    assert code == 2 and lines[-1].startswith("REFUSED: no planned call fits under the cap")
    assert not provider.calls and not cli.RepoPaths(repo).ledger.exists()


def test_dry_run_prints_count_per_image_cost_and_total_vs_cap(repo: Path) -> None:
    code, lines = _run(repo, ["--tier", "all", "--cap", "15"], FakeImageProvider())
    planned = next(line for line in lines if line.startswith("planned: "))
    assert code == 0 and "per image" in planned and planned.endswith("vs cap 15.00 EUR")
    assert "cut by cap: none" in lines


def test_ui_art_keys_are_in_the_manifest_with_v1_tab_icons_real() -> None:
    manifest = json.loads((STATIC / "assets" / "manifest.json").read_text(encoding="utf-8"))
    for art in UI_ART:
        entry = manifest[art.key]
        assert entry["file"] == art.file and (art.v1 or entry["prompt"])
        if art.v1:
            assert (entry["status"], entry["source"]) == ("real", "v1")
        elif art.hand:  # owner art copied in by hand (M13.6): never generated
            assert entry["source"] == "manual"
            assert art.key not in derive_tiers(manifest).p1
        else:  # a placeholder until M12.2 generated it, never v1 art
            generated = str(entry["source"]).startswith("generated:")
            assert (entry["status"], generated) in {("placeholder", False), ("real", True)}
    tiers = derive_tiers(manifest)
    assert tiers.p1.get("scene.defeat") == "UI chrome"
    assert tiers.p1.get("ui_icon.tab-more") == "UI chrome"
    assert "ui_icon.tab-play" not in tiers.p1 and "ui_icon.tab-play" not in tiers.p2


def test_ui_art_keys_are_derived_specs() -> None:
    keys = {s.key for s in derive_specs(STATIC)}
    assert {a.key for a in UI_ART} <= keys
