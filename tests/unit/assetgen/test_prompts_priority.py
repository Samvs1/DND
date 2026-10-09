"""Prompts, references, sheets and the committed ASSET_PRIORITY.md (Addendum B.1, B.3)."""

import json
import random
import re
import zlib
from pathlib import Path

from aidm.server.asset_prompts import load_style_bible
from aidm.server.assetgen import cli
from aidm.server.assetgen.costs import load_price_table
from aidm.server.assetgen.plan import build_calls, select_keys
from aidm.server.assetgen.priority import derive_tiers, render_priority
from aidm.server.assetgen.prompts import REFERENCE_TEXT, SCRIBE_REFS, RefSources, references_for
from aidm.server.assetgen.provider import SHEET_MARK
from aidm.server.assetgen.synthetic_png import png_size, synthetic_png
from tests.unit.assetgen.helpers import REPO_ROOT, make_repo, small_manifest
from tests.unit.assets.test_assets_todo import DENYLIST

BIBLE = load_style_bible()
TABLE = load_price_table()


def _real_manifest() -> dict[str, dict[str, object]]:
    return json.loads(cli.RepoPaths(REPO_ROOT).manifest.read_text(encoding="utf-8"))


def _calls(tmp_path: Path, tier: int = 2):
    v1 = make_repo(tmp_path)
    manifest = small_manifest()
    static = tmp_path / "aidm" / "web" / "static"
    keys = select_keys(manifest, static, derive_tiers(manifest), tier=tier).keys
    return build_calls(manifest, keys, bible=BIBLE, table=TABLE, refs=RefSources(static, v1))


def test_every_prompt_starts_with_the_style_bible_prefix(tmp_path: Path) -> None:
    calls = _calls(tmp_path)
    assert calls and all(c.request.prompt.startswith(BIBLE.prefix) for c in calls)


def test_portraits_and_scenes_use_real_references_through_edit(tmp_path: Path) -> None:
    calls = {c.label: c for c in _calls(tmp_path)}
    portrait = calls["portrait.race.elf.f"].request
    assert portrait.endpoint == "edit" and len(portrait.references) == 3
    assert f"{REFERENCE_TEXT} Create a new subject: A female Elf" in portrait.prompt
    banner = calls["region_banner.tier1"].request
    assert len(banner.references) == 2 and "dawn" in banner.prompt
    assert all(p.is_file() for c in calls.values() for p in c.request.references)


def test_icons_and_tokens_are_batched_into_sheets_of_at_most_16(tmp_path: Path) -> None:
    sheets = [c for c in _calls(tmp_path) if c.label.startswith("sheet ")]
    assert {c.label for c in sheets} == {"sheet icon 1/1", "sheet token 1/1"}
    for call in sheets:
        assert SHEET_MARK in call.request.prompt and len(call.keys) <= 16
        assert len(call.request.references) == 1 and call.request.transparent
    icon = next(c for c in sheets if c.label.startswith("sheet icon"))
    assert icon.keys == ("item_icon.tool", "condition_icon.asleep")


def test_real_manifest_sheets_hold_16_cells_and_singles_one_entry() -> None:
    manifest = _real_manifest()
    static = cli.RepoPaths(REPO_ROOT).static_dir
    keys = select_keys(manifest, static, derive_tiers(manifest), tier=1).keys
    calls = build_calls(manifest, keys, bible=BIBLE, table=TABLE, refs=RefSources(static, None))
    sheets = [c for c in calls if c.label.startswith("sheet ")]
    # P1 tokens were installed in M10.5 (installed keys are skipped), so only bounds remain.
    assert all(len(c.keys) <= 16 for c in sheets)
    assert all(len(c.keys) == 1 for c in calls if c not in sheets)
    assert sum(c.estimate(TABLE, None) for c in calls) < 8.0


def test_missing_references_fall_back_to_generate(tmp_path: Path) -> None:
    manifest = small_manifest()
    refs = RefSources(tmp_path / "nowhere", None)
    calls = build_calls(manifest, ["portrait.race.elf.f"], bible=BIBLE, table=TABLE, refs=refs)
    assert calls[0].request.endpoint == "generate" and REFERENCE_TEXT not in calls[0].request.prompt


def test_prompts_name_no_game_studio_or_franchise(tmp_path: Path) -> None:
    for call in _calls(tmp_path):
        for term in DENYLIST:
            assert re.search(term, call.request.prompt, re.I) is None, term


def test_committed_asset_priority_is_fresh() -> None:
    lines: list[str] = []
    assert cli.main(["--check-priority"], root=REPO_ROOT, out=lines.append) == 0, lines


def test_asset_priority_is_deterministic_and_order_independent() -> None:
    manifest = _real_manifest()
    items = list(manifest.items())
    random.Random(7).shuffle(items)
    first = render_priority(derive_tiers(manifest))
    assert first == render_priority(derive_tiers(dict(items)))


def test_p1_follows_the_b1_rules_on_the_real_manifest() -> None:
    manifest = _real_manifest()
    tiers = derive_tiers(manifest)
    labels = list(tiers.p1.values())
    assert labels.count("frequent monster") == 30 and labels.count("region banner") == 6
    assert labels.count("wizard portrait") == 18
    assert "portrait.npc.werewolf-human" in tiers.p1 and "portrait.npc.werewolf-wolf" in tiers.p2
    assert {"item_icon.tool", "spell_icon.school.cold"} <= set(tiers.p1)
    for key in [*tiers.p1, *tiers.p2]:
        entry = manifest[key]
        generated = str(entry["source"]).startswith("generated:")
        assert entry["source"] != "v1" and (entry["status"] == "placeholder" or generated), key
        assert entry["kind"] not in ("music", "sfx"), key


def _rgba_rows(data: bytes, width: int) -> list[bytes]:
    idat = data[data.index(b"IDAT") + 4 :]
    raw = zlib.decompress(idat[: idat.index(b"IEND") - 8])
    stride = width * 4 + 1
    return [raw[i + 1 : i + stride] for i in range(0, len(raw), stride)]


def test_fake_sheet_png_has_transparent_corners_and_a_4x4_grid() -> None:
    data = synthetic_png(32, 32, "seed", sheet=True)
    assert png_size(data) == (32, 32) and data == synthetic_png(32, 32, "seed", sheet=True)
    rows = _rgba_rows(data, 32)
    corners = (rows[0][3], rows[0][-1], rows[-1][3], rows[-1][-1])
    assert corners == (0, 0, 0, 0)
    centres = {
        rows[4 + 8 * r][(4 + 8 * c) * 4 : (4 + 8 * c) * 4 + 4] for r in range(4) for c in range(4)
    }
    assert len(centres) == 16 and all(px[3] == 255 for px in centres)


def test_scribe_poses_use_his_own_art_as_references(tmp_path: Path) -> None:
    for rel in SCRIBE_REFS + ("img/portraits/fighter_cropped.png",):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"x")
    sources = RefSources(static_dir=tmp_path)
    for key in ("portrait.scribe.welcome", "portrait.scribe.rewrite"):
        refs = references_for("portrait", sources, key=key)
        assert [p.relative_to(tmp_path).as_posix() for p in refs] == list(SCRIBE_REFS)
    other = references_for("portrait", sources, key="portrait.npc.acolyte")
    assert [p.name for p in other] == ["fighter_cropped.png"]
