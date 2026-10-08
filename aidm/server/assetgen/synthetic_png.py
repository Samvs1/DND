"""Deterministic synthetic RGBA PNGs for the fake image provider (no Pillow needed).

`synthetic_png(width, height, seed, sheet=...)` draws on a fully transparent background either a
4x4 grid of opaque coloured cells with transparent gutters (a sprite sheet) or one centred opaque
square (a single image). The same arguments always give the same bytes.

Public API: `synthetic_png`, `png_size`.
"""

import hashlib
import struct
import zlib

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
SHEET_GRID = 4


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def _colour(seed: str, index: int) -> bytes:
    digest = hashlib.sha256(f"{seed}:{index}".encode()).digest()
    return bytes((digest[0] | 0x20, digest[1] | 0x20, digest[2] | 0x20, 255))


def _pixel(x: int, y: int, width: int, height: int, seed: str, sheet: bool) -> bytes:
    if sheet:
        cell_w, cell_h = width // SHEET_GRID, height // SHEET_GRID
        if cell_w == 0 or cell_h == 0:
            return b"\x00\x00\x00\x00"
        cx, cy = x % cell_w, y % cell_h
        gutter_x, gutter_y = max(1, cell_w // 8), max(1, cell_h // 8)
        inside = gutter_x <= cx < cell_w - gutter_x and gutter_y <= cy < cell_h - gutter_y
        index = (y // cell_h) * SHEET_GRID + x // cell_w
        return _colour(seed, index) if inside else b"\x00\x00\x00\x00"
    inside = width // 4 <= x < width - width // 4 and height // 4 <= y < height - height // 4
    return _colour(seed, 0) if inside else b"\x00\x00\x00\x00"


def synthetic_png(width: int, height: int, seed: str, *, sheet: bool) -> bytes:
    """An RGBA PNG with transparent corners; a 4x4 cell grid when `sheet`."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows += _pixel(x, y, width, height, seed, sheet)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        PNG_MAGIC
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )


def png_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) of PNG bytes, None when the bytes are not a PNG."""
    if len(data) < 24 or data[:8] != PNG_MAGIC:
        return None
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)
