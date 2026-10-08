"""Pillow image builders for the pipeline tests (noise images pass the auto-checks)."""

import io
import random

from PIL import Image


def noise_png(width: int, height: int, seed: int = 1, *, alpha: bool = False) -> bytes:
    rng = random.Random(seed)
    image = Image.frombytes("RGB", (width, height), rng.randbytes(width * height * 3))
    rgba = image.convert("RGBA")
    if alpha:
        mask = Image.new("L", (width, height), 0)
        mask.paste(255, (width // 4, height // 4, width * 3 // 4, height * 3 // 4))
        rgba.putalpha(mask)
    buffer = io.BytesIO()
    rgba.save(buffer, format="PNG")
    return buffer.getvalue()


def flat_png(width: int, height: int, colour: tuple[int, int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def bordered_png(width: int, height: int) -> bytes:
    inner = Image.open(io.BytesIO(noise_png(width // 2, height // 2))).convert("RGBA")
    canvas = Image.new("RGBA", (width, height), (20, 20, 20, 255))
    canvas.paste(inner, (width // 4, height // 4))
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def pixel(image: Image.Image, xy: tuple[int, int]) -> tuple[int, ...]:
    value = image.convert("RGBA").getpixel(xy)
    assert isinstance(value, tuple)
    return value


def spread(image: Image.Image) -> tuple[int, int]:
    values = [int(v) for v in image.convert("L").tobytes()]
    return min(values), max(values)
