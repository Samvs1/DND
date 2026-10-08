"""Final human review sheets (Addendum B.5 step 6).

`build_final_review` reads the manifest and writes `FINAL_REVIEW.png` (an overview montage of every
installed `generated:*` asset plus 3 v1 references, at most 2000 px wide) and `FINAL_REVIEW_<n>.png`
detail sheets, grouped by kind (portraits, banners, tokens, icons), each tile labelled with its key
and preceded by a row of 3 real v1 reference images. Transparent images sit on a checkerboard.

Public API: `build_final_review`, `generated_keys`, `GROUPS`.
"""

import json
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

GROUPS: dict[str, tuple[str, ...]] = {
    "portraits": ("portrait",),
    "banners": ("region_banner", "zone_card"),
    "tokens": ("monster_token",),
    "icons": ("item_icon", "spell_icon", "condition_icon"),
}
FONT_SIZE = 14
MARGIN = 10
COLUMNS = 5
PER_SHEET = 15
OVERVIEW_WIDTH = 2000
BACKGROUND = (34, 30, 38)
TEXT = (240, 232, 214)
CHECKER = ((70, 66, 76), (52, 48, 58))
REFS = 3


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=FONT_SIZE)


def generated_keys(manifest: dict[str, Any], static: Path) -> dict[str, list[str]]:
    """Group the installed generated keys (file present) by review group."""
    out: dict[str, list[str]] = {name: [] for name in GROUPS}
    for key in sorted(manifest):
        entry = manifest[key]
        if not str(entry.get("source", "")).startswith("generated:"):
            continue
        if not (static / entry["file"]).is_file():
            continue
        for name, kinds in GROUPS.items():
            if entry["kind"] in kinds:
                out[name].append(key)
    return out


def _v1_refs(manifest: dict[str, Any], static: Path, group: str) -> list[str]:
    def v1(kind: str, prefix: str) -> list[str]:
        keys = [
            k
            for k, e in sorted(manifest.items())
            if e["kind"] == kind and k.startswith(prefix) and e.get("source") == "v1"
        ]
        return [k for k in keys if (static / manifest[k]["file"]).is_file()]

    if group == "tokens":
        found = v1("monster_token", "")
        if len(found) >= REFS:
            return found[:REFS]
    return v1("portrait", "portrait.class.")[:REFS]


def _checker(size: tuple[int, int]) -> Image.Image:
    base = Image.new("RGB", size, CHECKER[0])
    draw = ImageDraw.Draw(base)
    for y in range(0, size[1], 16):
        for x in range(0, size[0], 16):
            if (x // 16 + y // 16) % 2:
                draw.rectangle((x, y, x + 15, y + 15), fill=CHECKER[1])
    return base


def _tile(path: Path, side: int) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    image.thumbnail((side, side), Image.Resampling.LANCZOS)
    tile = _checker((side, side))
    tile.paste(image, ((side - image.width) // 2, (side - image.height) // 2), image)
    return tile


def _label(draw: ImageDraw.ImageDraw, origin: tuple[int, int], text: str, width: int) -> None:
    per_line = max(8, width // 8)
    for n, i in enumerate(range(0, min(len(text), per_line * 2), per_line)):
        draw.text(
            (origin[0], origin[1] + n * (FONT_SIZE + 2)),
            text[i : i + per_line],
            fill=TEXT,
            font=_font(),
        )


def _grid(
    title: str, refs: list[tuple[str, Path]], items: list[tuple[str, Path]], side: int, cols: int
) -> Image.Image:
    cell_w, cell_h = side + MARGIN, side + 2 * (FONT_SIZE + 2) + MARGIN
    rows = -(-len(items) // cols) if items else 0
    top = FONT_SIZE + 2 * MARGIN
    width = cols * cell_w + MARGIN
    sheet = Image.new("RGB", (width, top + cell_h * (1 + rows) + MARGIN), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    draw.text((MARGIN, MARGIN), title, fill=TEXT, font=_font())
    for i, (label, path) in enumerate(refs):
        sheet.paste(_tile(path, side), (MARGIN + i * cell_w, top))
        _label(draw, (MARGIN + i * cell_w, top + side + 2), "v1 ref " + label, side)
    for i, (label, path) in enumerate(items):
        x, y = MARGIN + (i % cols) * cell_w, top + cell_h * (1 + i // cols)
        sheet.paste(_tile(path, side), (x, y))
        _label(draw, (x, y + side + 2), label, side)
    return sheet


def _save(image: Image.Image, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    image.save(tmp, format="PNG")
    os.replace(tmp, out)


def _overview(
    groups: dict[str, list[tuple[str, Path]]], refs: list[tuple[str, Path]], out: Path
) -> None:
    side, gap = 56, 4
    cols = (OVERVIEW_WIDTH - 2 * MARGIN) // (side + gap)
    total = sum(len(v) for v in groups.values())
    rows = sum(-(-len(v) // cols) for v in groups.values() if v)
    height = 2 * MARGIN + (FONT_SIZE + 6) * (len(groups) + 2) + (rows + 1) * (side + gap)
    sheet = Image.new("RGB", (OVERVIEW_WIDTH, height), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    y = MARGIN
    draw.text(
        (MARGIN, y),
        f"FINAL REVIEW overview: {total} generated assets, 3 v1 refs first",
        fill=TEXT,
        font=_font(),
    )
    y += FONT_SIZE + 6
    for i, (_, path) in enumerate(refs):
        sheet.paste(_tile(path, side), (MARGIN + i * (side + gap), y))
    y += side + gap
    for name, items in groups.items():
        if not items:
            continue
        draw.text((MARGIN, y), f"{name} ({len(items)})", fill=TEXT, font=_font())
        y += FONT_SIZE + 6
        for i, (_, path) in enumerate(items):
            sheet.paste(
                _tile(path, side),
                (MARGIN + (i % cols) * (side + gap), y + (i // cols) * (side + gap)),
            )
        y += -(-len(items) // cols) * (side + gap)
    _save(sheet.crop((0, 0, OVERVIEW_WIDTH, min(height, y + MARGIN))), out)


def build_final_review(manifest_path: Path, static: Path, out_dir: Path) -> list[Path]:
    """Write the overview and the detail sheets; return every written path (overview first)."""
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    keys = generated_keys(manifest, static)
    paths = {k: static / manifest[k]["file"] for ks in keys.values() for k in ks}
    items = {g: [(k, paths[k]) for k in ks] for g, ks in keys.items()}
    overview_refs = [
        (k, static / manifest[k]["file"]) for k in _v1_refs(manifest, static, "portraits")
    ]
    written = [out_dir / "FINAL_REVIEW.png"]
    _overview(items, overview_refs, written[0])
    number = 0
    for group, entries in items.items():
        refs = [(k, static / manifest[k]["file"]) for k in _v1_refs(manifest, static, group)]
        side = 160 if group in ("tokens", "icons") else 200
        for start in range(0, len(entries), PER_SHEET):
            number += 1
            page = entries[start : start + PER_SHEET]
            title = f"{group} {start + 1}-{start + len(page)} of {len(entries)} (sheet {number})"
            out = out_dir / f"FINAL_REVIEW_{number}.png"
            _save(_grid(title, refs, page, side, COLUMNS), out)
            written.append(out)
    return written
