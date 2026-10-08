"""M10.5 pipeline fixes: specks, blob fallback, uniform band, retry mode."""

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from aidm.server.assetgen import cli
from aidm.server.assetgen.autocheck import CheckSpec, check_image
from aidm.server.assetgen.fake_provider import FakeImageProvider
from aidm.server.assetgen.ledger import load_ledger
from aidm.server.assetgen.plan import select_keys
from aidm.server.assetgen.priority import derive_tiers
from aidm.server.assetgen.provider import ImageProvider, ImageRequest, ImageResult, ModelInfo
from aidm.server.assetgen.slicer import fit_cell, slice_sheet, slice_sheet_noted
from tests.unit.assetgen.helpers import make_repo, small_manifest
from tests.unit.assetgen.imgs import flat_png, noise_png


def _blank(size: int = 256) -> Image.Image:
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def _bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _patch(image: Image.Image, box: tuple[int, int, int, int], seed: int) -> None:
    w, h = box[2] - box[0], box[3] - box[1]
    tile = Image.open(io.BytesIO(noise_png(w, h, seed))).convert("RGBA")
    image.paste(tile, box[:2])


def _opaque_pixels(image: Image.Image) -> int:
    return sum(1 for a in image.getchannel("A").tobytes() if a > 16)


def test_priority_tiers_ignore_installed_generated_art() -> None:
    manifest = small_manifest()
    before = derive_tiers(manifest)
    key = "portrait.race.elf.f"
    manifest[key] = {**manifest[key], "status": "real", "source": "generated:test-model"}
    after = derive_tiers(manifest)
    assert (after.p1, after.p2) == (before.p1, before.p2)
    static = Path("nowhere")
    assert key in select_keys(small_manifest(), static, before).keys
    chosen = select_keys(manifest, static, after)
    assert key not in chosen.keys and (key, "has real or v1 art") in chosen.skipped


def test_slicer_removes_specks_from_neighbouring_cells() -> None:
    cell = _blank(128)
    _patch(cell, (30, 30, 98, 98), 1)
    _patch(cell, (0, 0, 6, 6), 2)  # a far corner fragment
    cut = fit_cell(cell, (64, 64))
    assert cut.getchannel("A").getpixel((1, 1)) == 0
    assert _opaque_pixels(cut) > 64 * 64 * 0.7


def test_slicer_keeps_a_flame_within_the_gap() -> None:
    cell = _blank(128)
    _patch(cell, (30, 60, 98, 110), 1)
    _patch(cell, (56, 40, 72, 54), 3)  # 6 px above the main shape
    cut = fit_cell(cell, (128, 128))
    assert cut.getbbox() is not None
    box = cut.getchannel("A").point([0] * 17 + [255] * 239).getbbox()
    assert box is not None and (box[3] - box[1]) > 0.9 * 128 - 8 * 2


def test_blob_fallback_places_two_icons_left_and_right() -> None:
    sheet = _blank()
    _patch(sheet, (20, 90, 100, 170), 4)  # straddles grid cells, none of 0 or 1
    _patch(sheet, (150, 90, 230, 170), 5)
    keys = ["item_icon.tool", "spell_icon.school.cold"]
    sizes = {k: (64, 64) for k in keys}
    cuts, note = slice_sheet_noted(_bytes(sheet), keys, sizes)
    assert "blob" in note
    left = Image.open(io.BytesIO(cuts[keys[0]])).convert("RGBA")
    right = Image.open(io.BytesIO(cuts[keys[1]])).convert("RGBA")
    assert _opaque_pixels(left) > 1500 and _opaque_pixels(right) > 1500
    assert left.size == (64, 64)


def test_blob_count_mismatch_falls_back_to_the_grid_with_a_note() -> None:
    sheet = _blank()
    _patch(sheet, (20, 90, 100, 170), 4)
    _patch(sheet, (150, 90, 230, 170), 5)
    _patch(sheet, (100, 10, 140, 50), 6)
    keys = ["item_icon.a", "item_icon.b"]
    _, note = slice_sheet_noted(_bytes(sheet), keys, {k: (32, 32) for k in keys})
    assert "blob count 3 != 2" in note


def test_full_sheet_still_uses_the_grid() -> None:
    sheet = _blank()
    for i in range(16):
        row, col = divmod(i, 4)
        _patch(sheet, (col * 64 + 12, row * 64 + 12, col * 64 + 52, row * 64 + 52), i + 10)
    keys = [f"item_icon.k{i}" for i in range(16)]
    cuts, note = slice_sheet_noted(_bytes(sheet), keys, {k: (32, 32) for k in keys})
    assert note == "" and len(cuts) == 16
    assert cuts == slice_sheet(_bytes(sheet), keys, {k: (32, 32) for k in keys})


def test_uniform_white_band_fails_an_opaque_banner() -> None:
    banner = Image.open(io.BytesIO(noise_png(256, 64))).convert("RGBA")
    banner.paste((255, 255, 255, 255), (0, 38, 256, 64))
    result = check_image(_bytes(banner), CheckSpec())
    assert not result.ok and "uniform_band:bottom" in result.reasons


def test_dark_vignette_edges_are_not_a_band() -> None:
    banner = Image.open(io.BytesIO(noise_png(256, 64))).convert("RGBA")
    dark = Image.new("RGBA", (256, 20), (10, 10, 12, 255))
    banner.paste(Image.blend(banner.crop((0, 0, 256, 20)), dark, 0.9), (0, 0))
    result = check_image(_bytes(banner), CheckSpec())
    assert not any(r.startswith("uniform_band") for r in result.reasons)
    assert check_image(noise_png(256, 64), CheckSpec()).ok
    assert check_image(flat_png(8, 8, (0, 0, 0, 0)), CheckSpec(transparent=True)).reasons


class RecordingProvider:
    name = "recording"

    def __init__(self) -> None:
        self.inner: ImageProvider = FakeImageProvider()
        self.requests: list[ImageRequest] = []

    def list_models(self) -> list[ModelInfo]:
        return self.inner.list_models()

    def generate(self, request: ImageRequest, model: str) -> ImageResult:
        self.requests.append(request)
        return self.inner.generate(request, model)

    def edit(self, request: ImageRequest, model: str) -> ImageResult:
        self.requests.append(request)
        return self.inner.edit(request, model)


def _stage(root: Path, key: str, quality: str, name: str) -> None:
    staging = cli.RepoPaths(root).staging
    staging.mkdir(parents=True, exist_ok=True)
    meta = {"keys": [key], "quality": quality, "model": "m", "prompt": "p"}
    (staging / f"{name}.json").write_text(json.dumps(meta), encoding="utf-8")


def _review(root: Path) -> Path:
    path = root / "review.json"
    items = {
        "region_banner.tier1": {"verdict": "retry", "prompt_fix": "fill the whole canvas"},
        "zone_card.cave": {"verdict": "accept"},
        "portrait.race.elf.f": {"verdict": "retry", "prompt_fix": "calmer pose"},
    }
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def _retry(root: Path, provider: RecordingProvider, *extra: str) -> tuple[int, list[str]]:
    lines: list[str] = []
    argv = ["--retry", str(_review(root)), "--v1-root", str(root / "v1"), *extra]
    return cli.main(argv, root=root, provider=provider, out=lines.append), lines


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    make_repo(tmp_path)
    return tmp_path


def test_retry_dry_run_lists_only_retry_keys_and_calls_nothing(repo: Path) -> None:
    provider = RecordingProvider()
    code, lines = _retry(repo, provider)
    text = "\n".join(lines)
    assert code == 0 and "DRY RUN" in text and "retry review.json: 2 entries" in text
    assert provider.requests == [] and not cli.RepoPaths(repo).ledger.exists()


def test_retry_calls_only_retry_keys_with_the_fix_and_counts_in_the_ledger(repo: Path) -> None:
    provider = RecordingProvider()
    code, _ = _retry(repo, provider, "--yes")
    assert code == 0 and len(provider.requests) == 2
    prompts = " ".join(r.prompt for r in provider.requests)
    assert "fill the whole canvas" in prompts and "calmer pose" in prompts
    assert all(r.prompt.startswith(cli.load_style_bible().prefix) for r in provider.requests)
    entries = load_ledger(cli.RepoPaths(repo).ledger).entries
    assert sorted(k for e in entries for k in e.keys) == [
        "portrait.race.elf.f",
        "region_banner.tier1",
    ]
    assert all(e.quality == "medium" for e in entries)


def test_retry_refuses_a_fourth_attempt_and_goes_high_after_two_medium(repo: Path) -> None:
    for n in range(3):
        _stage(repo, "portrait.race.elf.f", "medium", f"elf{n}")
    _stage(repo, "region_banner.tier1", "medium", "banner0")
    _stage(repo, "region_banner.tier1", "medium", "banner1")
    provider = RecordingProvider()
    code, lines = _retry(repo, provider, "--yes")
    assert code == 0
    assert any("portrait.race.elf.f: max_attempts_reached" in line for line in lines)
    assert len(provider.requests) == 1
    assert provider.requests[0].quality == "high"
    assert "fill the whole canvas" in provider.requests[0].prompt
