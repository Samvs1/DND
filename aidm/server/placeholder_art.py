"""Shared SVG building blocks for placeholder art (Addendum A.3): palette, seeding, frame, marker.

Everything here is pure and deterministic: no clock, no randomness beyond `seeded(...)`.

Public API: `PALETTE`, `Size`, `seeded`, `pick_hue`, `escape`, `svg_document`, `initials`.
"""

import hashlib
import random
from colorsys import hls_to_rgb
from xml.sax.saxutils import escape as _escape

type Size = tuple[int, int]

PALETTE: dict[str, str] = {
    "ink": "#090706",
    "stone": "#17120f",
    "stone2": "#2e241c",
    "gold": "#d2a94e",
    "gold_dim": "#7d6128",
    "parchment": "#ead9ab",
    "muted": "#9b8d73",
}


def seeded(kind: str, slug: str) -> random.Random:
    """A RNG seeded from the key hash, so the same key always draws the same placeholder."""
    digest = hashlib.sha256(f"{kind}/{slug}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def pick_hue(rng: random.Random, *, lightness: float = 0.42, sat: float = 0.35) -> str:
    """A muted colour with a random hue (fixed lightness and saturation keep the dark palette)."""
    red, green, blue = hls_to_rgb(rng.random(), lightness, sat)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def escape(text: str) -> str:
    return _escape(text, {'"': "&quot;"})


def initials(text: str) -> str:
    """First letter of the first word, upper case ('?' for an empty name)."""
    for char in text:
        if char.isalnum():
            return char.upper()
    return "?"


def _marker(width: int) -> str:
    """The small corner glyph that marks a picture as a placeholder (a gold diamond)."""
    size = max(10, min(18, width // 14))
    margin = size // 2 + 3
    cx, cy = width - margin, margin
    pts = f"{cx},{cy - size // 2} {cx + size // 2},{cy} {cx},{cy + size // 2} {cx - size // 2},{cy}"
    return (
        f'<g class="placeholder-mark"><polygon points="{pts}" fill="{PALETTE["ink"]}" '
        f'stroke="{PALETTE["gold"]}" stroke-width="1.5"/>'
        f'<circle cx="{cx}" cy="{cy}" r="1.6" fill="{PALETTE["gold"]}"/></g>'
    )


def svg_document(size: Size, label: str, body: str, *, base: str = PALETTE["stone"]) -> str:
    """Wrap `body` in an SVG: dark gradient background, gold frame, placeholder mark."""
    width, height = size
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{escape(label)}">'
        f"<title>{escape(label)}</title>"
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{base}"/><stop offset="1" stop-color="{PALETTE["ink"]}"/>'
        f"</linearGradient></defs>"
        f'<rect width="{width}" height="{height}" fill="url(#bg)"/>'
        f"{body}"
        f'<rect x="1.5" y="1.5" width="{width - 3}" height="{height - 3}" fill="none" '
        f'stroke="{PALETTE["gold_dim"]}" stroke-width="3"/>'
        f"{_marker(width)}</svg>"
    )
