"""4x4 slicer and contact sheet (Addendum B.5, B.6)."""

import io
import json
from pathlib import Path

from PIL import Image

from aidm.server.assetgen.contactsheet import LabelledImage, render_contact_sheet
from aidm.server.assetgen.review_cli import contact_sheet_main
from aidm.server.assetgen.slicer import cell_boxes, slice_sheet
from aidm.server.assetgen.synthetic_png import synthetic_png
from tests.unit.assetgen.helpers import make_repo
from tests.unit.assetgen.imgs import noise_png, pixel, spread


def _centre(data: bytes) -> tuple[int, ...]:
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    value = image.getpixel((image.width // 2, image.height // 2))
    assert isinstance(value, tuple)
    return value


def test_slicer_splits_a_4x4_sheet_in_cell_order() -> None:
    sheet = synthetic_png(256, 256, "icons", sheet=True)
    source = Image.open(io.BytesIO(sheet)).convert("RGBA")
    keys = [f"item_icon.k{i}" for i in range(16)]
    sizes = {k: (64, 64) for k in keys}
    cuts = slice_sheet(sheet, keys, sizes)
    assert list(cuts) == keys
    colours = set()
    for index, key in enumerate(keys):
        left, top, right, bottom = cell_boxes(256, 256)[index]
        expected = pixel(source, ((left + right) // 2, (top + bottom) // 2))
        assert _centre(cuts[key]) == expected
        colours.add(expected)
        out = Image.open(io.BytesIO(cuts[key]))
        assert out.size == (64, 64) and out.mode == "RGBA"
        assert pixel(out, (0, 0))[3] == 0
    assert len(colours) == 16


def test_slicer_fits_non_square_targets_and_keeps_alpha() -> None:
    sheet = synthetic_png(256, 256, "tok", sheet=True)
    cuts = slice_sheet(sheet, ["monster_token.a"], {"monster_token.a": (96, 48)})
    out = Image.open(io.BytesIO(cuts["monster_token.a"]))
    assert out.size == (96, 48) and pixel(out, (0, 0))[3] == 0 and pixel(out, (48, 24))[3] == 255


def test_contact_sheet_has_labels_references_and_64px_renditions(tmp_path: Path) -> None:
    items = [
        LabelledImage(f"portrait.npc.k{i} (attempt 1)", noise_png(128, 128, i)) for i in range(12)
    ]
    refs = [
        LabelledImage("v1 ref a", noise_png(64, 64, 90)),
        LabelledImage("v1 ref b", noise_png(64, 64, 91)),
    ]
    out = render_contact_sheet(items, refs, "review 1", tmp_path / "review_1.png")
    image = Image.open(out)
    assert image.width >= 4 * 240 and image.height >= 4 * 240
    # label band under the first candidate holds light text pixels on the dark background
    top = 12 + 16 + 12 + 252 + 54 + 12
    band = image.crop((12, top + 240, 12 + 170, top + 240 + 54)).convert("L")
    assert spread(band)[1] > 200
    # the 64 px rendition sits at the right edge of the first candidate tile
    small = image.crop((12 + 240 - 64, top + 244, 12 + 240, top + 244 + 64)).convert("L")
    assert spread(small)[1] - spread(small)[0] > 50


def test_contact_sheet_refuses_more_than_twelve(tmp_path: Path) -> None:
    items = [LabelledImage(f"k{i}", noise_png(16, 16, i)) for i in range(13)]
    try:
        render_contact_sheet(items, [], "x", tmp_path / "x.png")
    except ValueError as exc:
        assert "12" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_contact_sheet_command_slices_staged_sheets_and_writes_the_index(tmp_path: Path) -> None:
    make_repo(tmp_path)
    staging = tmp_path / "artifacts" / "assets" / "candidates"
    staging.mkdir(parents=True)
    keys = ["monster_token.goblin", "monster_token.bandit"]
    (staging / "sheet_a__c1.png").write_bytes(synthetic_png(1024, 1024, "t", sheet=True))
    meta = {"keys": keys, "sheet": True, "model": "gpt-image-1.5", "prompt": "p", "cost_eur": 0.2}
    (staging / "sheet_a__c1.json").write_text(json.dumps(meta), encoding="utf-8")
    lines: list[str] = []
    assert contact_sheet_main([], tmp_path, lines.append) == 0
    base = tmp_path / "artifacts" / "assets"
    assert (base / "review_1.png").is_file()
    items = json.loads((base / "review_1.index.json").read_text(encoding="utf-8"))["items"]
    assert [i["key"] for i in items] == keys and items[0]["cost_eur"] == 0.1
    assert Image.open(base / items[0]["image"]).size == (256, 256)
