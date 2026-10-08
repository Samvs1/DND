"""Render a labelled contact sheet for the reviewer (Addendum B.5 step 2).

Layout: a title band, a top row with up to 2 v1 reference thumbnails, then up to 12 candidates in
a 4-column grid. Each candidate shows its image, a 64 px rendition beside it (for the readability
score) and a label line "key (attempt n)". The default Pillow font is used at a large size so the
labels can be read when the sheet is viewed as an image.

Public API: `MAX_CANDIDATES`, `LabelledImage`, `render_contact_sheet`.
"""

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MAX_CANDIDATES = 12
MAX_REFERENCES = 2
COLUMNS = 4
TILE = 240
SMALL = 64
LABEL_H = 54
MARGIN = 12
FONT_SIZE = 16
BACKGROUND = (34, 30, 38, 255)
TEXT = (240, 232, 214, 255)
CHECKER = ((70, 66, 76, 255), (52, 48, 58, 255))


@dataclass(frozen=True)
class LabelledImage:
    label: str
    image: bytes


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=FONT_SIZE)


def _checker(size: tuple[int, int]) -> Image.Image:
    base = Image.new("RGBA", size, CHECKER[0])
    draw = ImageDraw.Draw(base)
    for y in range(0, size[1], 16):
        for x in range(0, size[0], 16):
            if (x // 16 + y // 16) % 2:
                draw.rectangle((x, y, x + 15, y + 15), fill=CHECKER[1])
    return base


def _thumb(data: bytes, side: int) -> Image.Image:
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    image.thumbnail((side, side), Image.Resampling.LANCZOS)
    tile = _checker((side, side))
    tile.paste(image, ((side - image.width) // 2, (side - image.height) // 2), image)
    return tile


def _wrap(text: str, width: int) -> list[str]:
    return [text[i : i + width] for i in range(0, len(text), width)][:3] or [""]


def _cell(sheet: Image.Image, origin: tuple[int, int], item: LabelledImage, small: bool) -> None:
    x, y = origin
    sheet.paste(_thumb(item.image, TILE), (x, y))
    if small:
        sheet.paste(_thumb(item.image, SMALL), (x + TILE - SMALL, y + TILE + 4))
    draw = ImageDraw.Draw(sheet)
    width = (TILE - SMALL - 8) // 9 if small else TILE // 9
    for line, text in enumerate(_wrap(item.label, width)):
        draw.text((x, y + TILE + 4 + line * (FONT_SIZE + 2)), text, fill=TEXT, font=_font())


def render_contact_sheet(
    candidates: list[LabelledImage], references: list[LabelledImage], title: str, out: Path
) -> Path:
    """Write the sheet PNG to `out` (atomically) and return the path."""
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError(f"a contact sheet shows at most {MAX_CANDIDATES} candidates")
    cell_w, cell_h = TILE + MARGIN, TILE + LABEL_H + MARGIN
    rows = max(1, -(-len(candidates) // COLUMNS))
    top = FONT_SIZE + 2 * MARGIN
    ref_band = cell_h if references else 0
    sheet = Image.new(
        "RGBA", (COLUMNS * cell_w + MARGIN, top + ref_band + rows * cell_h + MARGIN), BACKGROUND
    )
    ImageDraw.Draw(sheet).text((MARGIN, MARGIN), title, fill=TEXT, font=_font())
    for i, ref in enumerate(references[:MAX_REFERENCES]):
        _cell(sheet, (MARGIN + i * cell_w, top), ref, small=False)
    for i, item in enumerate(candidates):
        origin = (MARGIN + (i % COLUMNS) * cell_w, top + ref_band + (i // COLUMNS) * cell_h)
        _cell(sheet, origin, item, small=True)
    buffer = io.BytesIO()
    sheet.convert("RGB").save(buffer, format="PNG")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_bytes(buffer.getvalue())
    tmp.replace(out)
    return out
