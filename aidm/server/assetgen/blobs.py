"""Foreground blobs of an RGBA image, in pure Pillow (no scipy).

The alpha channel (> FOREGROUND_ALPHA) is the foreground. It is reduced by `SCALE`, dilated so that
pieces separated by at most about `GAP` pixels join, and labelled by flood fill. Areas count the
real (undilated) foreground at the reduced scale. Used by the slicer to erase stray fragments of
neighbouring cells and to find icons that the model placed outside the 4x4 grid.

Public API: `Blob`, `find_blobs`, `blob_mask`, `drop_small`, `reading_order`.
"""

from dataclasses import dataclass

from PIL import Image, ImageFilter

FOREGROUND_ALPHA = 16
GAP = 8
SCALE = 4


@dataclass(frozen=True)
class Blob:
    label: int
    area: int
    box: tuple[int, int, int, int]  # full-resolution (left, top, right, bottom)


@dataclass(frozen=True)
class Labelled:
    blobs: tuple[Blob, ...]
    grid: list[int]  # label per reduced pixel, 0 = background
    size: tuple[int, int]  # reduced size (width, height)
    full: tuple[int, int]


def _reduced_mask(image: Image.Image) -> Image.Image:
    alpha = image.convert("RGBA").getchannel("A")
    mask = alpha.point([0] * (FOREGROUND_ALPHA + 1) + [255] * (255 - FOREGROUND_ALPHA))
    small = (max(1, -(-mask.width // SCALE)), max(1, -(-mask.height // SCALE)))
    return mask.resize(small, Image.Resampling.BOX).point([0] + [255] * 255)


def _flood(joined: bytes, width: int, height: int) -> tuple[list[int], int]:
    grid = [0] * (width * height)
    count = 0
    for start in range(width * height):
        if not joined[start] or grid[start]:
            continue
        count += 1
        grid[start] = count
        stack = [start]
        while stack:
            at = stack.pop()
            x, y = at % width, at // width
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                n = ny * width + nx
                if 0 <= nx < width and 0 <= ny < height and joined[n] and not grid[n]:
                    grid[n] = count
                    stack.append(n)
    return grid, count


def find_blobs(image: Image.Image) -> Labelled:
    """Label the foreground blobs; gaps up to about GAP pixels do not split a blob."""
    mask = _reduced_mask(image)
    width, height = mask.size
    radius = max(1, round(GAP / 2 / SCALE))
    joined = mask.filter(ImageFilter.MaxFilter(2 * radius + 1))
    grid, count = _flood(joined.tobytes(), width, height)
    solid = mask.tobytes()
    stats: dict[int, list[int]] = {}
    for at, label in enumerate(grid):
        if label and solid[at]:
            x, y = at % width, at // width
            s = stats.setdefault(label, [0, x, y, x, y])
            s[0] += 1
            s[1], s[2], s[3], s[4] = min(s[1], x), min(s[2], y), max(s[3], x), max(s[4], y)
    blobs = tuple(
        Blob(
            label,
            s[0],
            (
                s[1] * SCALE,
                s[2] * SCALE,
                min(image.width, (s[3] + 1) * SCALE),
                min(image.height, (s[4] + 1) * SCALE),
            ),
        )
        for label, s in sorted(stats.items())
    )
    return Labelled(blobs, grid, (width, height), image.size)


def blob_mask(found: Labelled, labels: set[int]) -> Image.Image:
    """Full-size L mask, 255 on the dilated regions of the given blob labels."""
    small = Image.new("L", found.size, 0)
    small.putdata([255 if v in labels else 0 for v in found.grid])
    return small.resize(found.full, Image.Resampling.NEAREST)


def drop_small(blobs: tuple[Blob, ...], fraction: float) -> list[Blob]:
    """The blobs whose area is at least `fraction` of the largest."""
    if not blobs:
        return []
    top = max(b.area for b in blobs)
    return [b for b in blobs if b.area >= fraction * top]


def reading_order(blobs: list[Blob]) -> list[Blob]:
    """Rows by centre y (tolerance: half the median blob height), then left to right."""
    if not blobs:
        return []
    heights = sorted(b.box[3] - b.box[1] for b in blobs)
    tolerance = max(1, heights[len(heights) // 2] // 2)
    by_y = sorted(blobs, key=lambda b: (b.box[1] + b.box[3]) / 2)
    rows: list[list[Blob]] = []
    anchor = 0.0
    for blob in by_y:
        centre = (blob.box[1] + blob.box[3]) / 2
        if not rows or centre - anchor > tolerance:
            rows.append([])
            anchor = centre
        rows[-1].append(blob)
    return [b for row in rows for b in sorted(row, key=lambda b: b.box[0])]
