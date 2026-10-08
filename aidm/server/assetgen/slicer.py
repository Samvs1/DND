"""Cut a 4x4 generated sheet into one PNG per key (modelled on v1 assets_src/slice.py).

Cells are numbered row by row, left to right; cell i belongs to `keys[i]` (the key order saved in
the candidate sidecar). Each cell is trimmed to the bounding box of its visible pixels (alpha), then
fitted into the manifest target size keeping the aspect ratio, centred on a transparent canvas.
A cell that is fully opaque (no alpha to trim) is cover-cropped to the target aspect instead. The
alpha channel is preserved. Unlike v1 there is no magenta keying: the sheet prompt asks for a
transparent background.

Small alpha fragments (under 10 percent of the largest piece, beyond a gap of about 8 px) are erased
from a cell: they belong to the neighbouring cell. A sheet with fewer than 16 entries may put icons
anywhere: when a grid cell is blank (or there are fewer than 16 keys), the foreground blobs of the
whole sheet are assigned to the keys in reading order if their count equals the number of keys;
otherwise the grid result is kept and, if a cell was blank, the reason is returned as a note.

Public API: `GRID`, `cell_boxes`, `slice_sheet`, `slice_sheet_noted`, `fit_cell`, `png_bytes`.
"""

import io
from collections.abc import Mapping, Sequence

from PIL import Image

from aidm.server.assetgen.blobs import Blob, blob_mask, drop_small, find_blobs, reading_order

GRID = 4
ALPHA_THRESHOLD = 8
PADDING_FRACTION = 0.04
SPECK_FRACTION = 0.10
SHEET_BLOB_FRACTION = 0.02


def cell_boxes(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """The 16 cell boxes, row by row, as (left, top, right, bottom)."""
    return [
        (
            round(col * width / GRID),
            round(row * height / GRID),
            round((col + 1) * width / GRID),
            round((row + 1) * height / GRID),
        )
        for row in range(GRID)
        for col in range(GRID)
    ]


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _visible_box(cell: Image.Image) -> tuple[int, int, int, int] | None:
    alpha = cell.getchannel("A").point(
        [0] * (ALPHA_THRESHOLD + 1) + [255] * (255 - ALPHA_THRESHOLD)
    )
    return alpha.getbbox()


def _is_opaque(cell: Image.Image) -> bool:
    return cell.getchannel("A").getextrema()[0] == 255


def _cover(cell: Image.Image, target: tuple[int, int]) -> Image.Image:
    width, height = cell.size
    want = target[0] / target[1]
    if width / height > want:
        new_w = round(height * want)
        left = (width - new_w) // 2
        cell = cell.crop((left, 0, left + new_w, height))
    else:
        new_h = round(width / want)
        top = (height - new_h) // 2
        cell = cell.crop((0, top, width, top + new_h))
    return cell.resize(target, Image.Resampling.LANCZOS)


def _erase(cell: Image.Image, mask: Image.Image) -> Image.Image:
    alpha = cell.getchannel("A")
    alpha.paste(0, mask=mask)
    cleaned = cell.copy()
    cleaned.putalpha(alpha)
    return cleaned


def drop_specks(cell: Image.Image) -> Image.Image:
    """Erase alpha fragments smaller than SPECK_FRACTION of the largest piece."""
    found = find_blobs(cell)
    keep = {b.label for b in drop_small(found.blobs, SPECK_FRACTION)}
    erase = {b.label for b in found.blobs} - keep
    if not erase:
        return cell
    return _erase(cell, blob_mask(found, erase))


def fit_cell(cell: Image.Image, target: tuple[int, int]) -> Image.Image:
    """Trim `cell` to its visible content and fit it into `target`, alpha preserved."""
    cell = cell.convert("RGBA")
    if _is_opaque(cell):
        return _cover(cell, target)
    cell = drop_specks(cell)
    box = _visible_box(cell)
    if box is None:
        return Image.new("RGBA", target, (0, 0, 0, 0))
    content = cell.crop(box)
    pad = max(1, round(min(target) * PADDING_FRACTION))
    room = (max(1, target[0] - 2 * pad), max(1, target[1] - 2 * pad))
    scale = min(room[0] / content.width, room[1] / content.height)
    size = (max(1, round(content.width * scale)), max(1, round(content.height * scale)))
    content = content.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", target, (0, 0, 0, 0))
    canvas.paste(content, ((target[0] - size[0]) // 2, (target[1] - size[1]) // 2), content)
    return canvas


def _blob_cells(image: Image.Image, count: int) -> tuple[list[Image.Image], str]:
    """One cleaned crop per blob in reading order, or a note when the count does not match."""
    found = find_blobs(image)
    blobs: list[Blob] = reading_order(drop_small(found.blobs, SHEET_BLOB_FRACTION))
    if len(blobs) != count:
        return [], f"blob count {len(blobs)} != {count} keys, grid cells used"
    everyone = {b.label for b in found.blobs}
    cells: list[Image.Image] = []
    for blob in blobs:
        others = everyone - {blob.label}
        cells.append(_erase(image, blob_mask(found, others)).crop(blob.box))
    return cells, ""


def slice_sheet_noted(
    sheet: bytes, keys: Sequence[str], sizes: Mapping[str, tuple[int, int]]
) -> tuple[dict[str, bytes], str]:
    """PNG bytes per key plus a note ("" when the grid was fine)."""
    image = Image.open(io.BytesIO(sheet)).convert("RGBA")
    boxes = cell_boxes(image.width, image.height)
    if len(keys) > len(boxes):
        raise ValueError(f"a 4x4 sheet holds at most {len(boxes)} keys, got {len(keys)}")
    cells = [image.crop(box) for box in boxes[: len(keys)]]
    note = ""
    blank = any(not _is_opaque(c) and _visible_box(c) is None for c in cells)
    if blank or len(keys) < len(boxes):
        blob_cells, reason = _blob_cells(image, len(keys))
        if blob_cells:
            cells, note = blob_cells, "icons found by blob, not by grid cell"
        elif blank:
            note = reason
    return {k: png_bytes(fit_cell(c, sizes[k])) for k, c in zip(keys, cells, strict=True)}, note


def slice_sheet(
    sheet: bytes, keys: Sequence[str], sizes: Mapping[str, tuple[int, int]]
) -> dict[str, bytes]:
    """PNG bytes per key: cell i of the sheet goes to `keys[i]`, sized `sizes[key]`."""
    return slice_sheet_noted(sheet, keys, sizes)[0]
