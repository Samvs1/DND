"""Automatic image checks run before a candidate reaches the reviewer (Addendum B.5 step 1).

`check_image` looks at PNG bytes with Pillow and returns a `CheckResult` listing every reason it
fails: wrong size (exact size, or only the aspect ratio when `expected_ratio` is given), no alpha
or opaque corners when transparency is required, a blank image (almost no pixel variance), a large
uniform opaque border, or an absurd file size. A failed check costs an attempt but no reviewer
attention.

Public API: `CheckSpec`, `CheckResult`, `check_image`, `reasons_for_request`.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageStat, UnidentifiedImageError

MIN_BYTES = 100
MAX_BYTES = 8_000_000
MIN_STDDEV = 3.0
BORDER_FRACTION = 0.1
BORDER_MAX_STDDEV = 2.0
RATIO_TOLERANCE = 0.02
CORNER_ALPHA_MAX = 16


@dataclass(frozen=True)
class CheckSpec:
    expected_size: tuple[int, int] | None = None
    expected_ratio: float | None = None
    transparent: bool = False


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    reasons: tuple[str, ...]


def _load(data: bytes) -> Image.Image | None:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (OSError, UnidentifiedImageError, ValueError):
        return None
    return image.convert("RGBA")


def _size_reasons(image: Image.Image, spec: CheckSpec) -> list[str]:
    width, height = image.size
    if spec.expected_size is not None and image.size != spec.expected_size:
        return [f"wrong size {width}x{height}, expected {spec.expected_size}"]
    if spec.expected_ratio is not None:
        ratio = width / height
        if abs(ratio - spec.expected_ratio) > RATIO_TOLERANCE * spec.expected_ratio:
            return [f"wrong aspect ratio {width}x{height}"]
    return []


def _alpha_at(alpha: Image.Image, point: tuple[int, int]) -> int:
    value = alpha.getpixel(point)
    return value if isinstance(value, int) else 255


def _alpha_min(image: Image.Image) -> int:
    low = image.getchannel("A").getextrema()[0]
    return int(low) if isinstance(low, int | float) else 255


def _alpha_reasons(image: Image.Image) -> list[str]:
    alpha = image.getchannel("A")
    low, high = alpha.getextrema()
    if low == 255 and high == 255:
        return ["no alpha channel content (fully opaque)"]
    width, height = image.size
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    if any(_alpha_at(alpha, c) > CORNER_ALPHA_MAX for c in corners):
        return ["corner pixels are not transparent"]
    return []


def _blank_reasons(image: Image.Image) -> list[str]:
    stat = ImageStat.Stat(image)
    if max(stat.stddev) < MIN_STDDEV:
        return ["image is blank (no pixel variance)"]
    return []


def _border_reasons(image: Image.Image) -> list[str]:
    width, height = image.size
    bx, by = max(1, int(width * BORDER_FRACTION)), max(1, int(height * BORDER_FRACTION))
    bands = (
        (0, 0, width, by),
        (0, height - by, width, height),
        (0, 0, bx, height),
        (width - bx, 0, width, height),
    )
    for box in bands:
        band = image.crop(box)
        if _alpha_min(band) < 255:
            return []
    uniform = all(max(ImageStat.Stat(image.crop(b)).stddev[:3]) < BORDER_MAX_STDDEV for b in bands)
    return ["image has a large uniform border"] if uniform else []


def check_image(data: bytes, spec: CheckSpec) -> CheckResult:
    """Run every check on PNG bytes; the result lists all failure reasons."""
    reasons: list[str] = []
    if len(data) < MIN_BYTES or len(data) > MAX_BYTES:
        reasons.append(f"file size {len(data)} bytes is not sane")
    image = _load(data)
    if image is None:
        return CheckResult(False, (*reasons, "not a readable image"))
    reasons += _size_reasons(image, spec)
    if spec.transparent:
        reasons += _alpha_reasons(image)
    reasons += _blank_reasons(image)
    reasons += _border_reasons(image)
    return CheckResult(not reasons, tuple(reasons))


def reasons_for_request(size: str, transparent: bool, data: bytes) -> list[str]:
    """Runner hook: check a generated image against its request (size string 'WxH')."""
    width, height = (int(p) for p in size.split("x"))
    spec = CheckSpec(expected_ratio=width / height, transparent=transparent)
    return list(check_image(data, spec).reasons)
