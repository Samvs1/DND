"""Landscape bodies for zone-card and region-banner placeholders, one drawing per terrain tag.

Pure functions returning SVG markup; `rng` is the key-seeded generator, so drawings are stable.

Public API: `scene_body`, `banner_body`, `TERRAINS`.
"""

import random
from collections.abc import Callable

from aidm.server.placeholder_art import PALETTE, Size, escape

type Scene = Callable[[int, int, random.Random], str]

HORIZON = 0.62


def _ground(w: int, h: int, color: str) -> str:
    top = round(h * HORIZON)
    return f'<rect y="{top}" width="{w}" height="{h - top}" fill="{color}"/>'


def _hills(w: int, h: int, rng: random.Random, color: str) -> str:
    top = round(h * HORIZON)
    peak = rng.randint(round(h * 0.12), round(h * 0.2))
    return (
        f'<path d="M0 {top}Q{w * 0.25:.0f} {top - peak} {w * 0.5:.0f} {top - peak // 3}'
        f'T{w} {top - peak // 2}V{top}z" fill="{color}"/>'
    )


def _trees(w: int, h: int, rng: random.Random) -> str:
    base = round(h * HORIZON) + 6
    out = []
    for _ in range(9):
        x, s = rng.randint(10, w - 10), rng.randint(round(h * 0.14), round(h * 0.28))
        out.append(
            f'<polygon points="{x},{base - s} {x - s // 3},{base} {x + s // 3},{base}" '
            f'fill="#2c4a2a"/>'
        )
    return "".join(out)


def _wilds(w: int, h: int, rng: random.Random) -> str:
    return _hills(w, h, rng, "#3a4a2c") + _ground(w, h, "#2a3320")


def _forest(w: int, h: int, rng: random.Random) -> str:
    return _ground(w, h, "#1f2c1a") + _trees(w, h, rng)


def _ruins(w: int, h: int, rng: random.Random) -> str:
    base = round(h * HORIZON) + 8
    cols = "".join(
        f'<rect x="{x}" y="{base - ch}" width="{w // 24}" height="{ch}" fill="#6a6256"/>'
        for x, ch in ((int(w * f), rng.randint(h // 8, h // 3)) for f in (0.2, 0.35, 0.55, 0.72))
    )
    return _ground(w, h, "#2f2a24") + cols


def _bridge(w: int, h: int, rng: random.Random) -> str:
    top = round(h * HORIZON)
    return (
        _ground(w, h, "#1f3347")
        + f'<path d="M0 {top}Q{w / 2:.0f} {top - h * 0.3:.0f} {w} {top}v10Q{w / 2:.0f} '
        f'{top - h * 0.2:.0f} 0 {top + 10}z" fill="#6a5a46"/>'
    )


def _cave(w: int, h: int, rng: random.Random) -> str:
    top = round(h * HORIZON)
    return (
        _ground(w, h, "#1a1612")
        + f'<path d="M{w * 0.2:.0f} {top}Q{w * 0.2:.0f} {h * 0.18:.0f} {w * 0.5:.0f} {h * 0.18:.0f}'
        f'T{w * 0.8:.0f} {top}z" fill="{PALETTE["ink"]}" stroke="#3a3128" stroke-width="6"/>'
    )


def _village(w: int, h: int, rng: random.Random) -> str:
    base = round(h * HORIZON) + 10
    out = []
    for f in (0.15, 0.42, 0.68):
        x, bw = int(w * f), w // 6
        bh = rng.randint(h // 8, h // 5)
        out.append(
            f'<rect x="{x}" y="{base - bh}" width="{bw}" height="{bh}" fill="#5a4632"/>'
            f'<polygon points="{x - 6},{base - bh} {x + bw // 2},{base - bh - bh // 2} '
            f'{x + bw + 6},{base - bh}" fill="#7a3a2c"/>'
        )
    return _ground(w, h, "#33301f") + "".join(out)


def _swamp(w: int, h: int, rng: random.Random) -> str:
    top = round(h * HORIZON)
    reeds = "".join(
        f'<path d="M{x} {top + 30}v-{rng.randint(20, 60)}" stroke="#5a7a3a" stroke-width="3"/>'
        for x in (rng.randint(8, w - 8) for _ in range(14))
    )
    return (
        _ground(w, h, "#26352a")
        + f'<ellipse cx="{w // 2}" cy="{top + 40}" rx="{w // 3}" ry="14" fill="#1a2a2a"/>'
        + reeds
    )


def _keep(w: int, h: int, rng: random.Random) -> str:
    base = round(h * HORIZON) + 8
    tw = w // 6
    towers = "".join(
        f'<rect x="{x}" y="{base - th}" width="{tw}" height="{th}" fill="#555050"/>'
        + "".join(
            f'<rect x="{x + i * tw // 3}" y="{base - th - 14}" width="{tw // 5}" '
            f'height="14" fill="#555050"/>'
            for i in range(3)
        )
        for x, th in ((int(w * 0.3), int(h * 0.4)), (int(w * 0.55), int(h * 0.3)))
    )
    return _ground(w, h, "#2a2622") + towers


def _crypt(w: int, h: int, rng: random.Random) -> str:
    base = round(h * HORIZON) + 20
    stones = "".join(
        f'<path d="M{x} {base}v-{sh}q{w // 40} -{w // 30} {w // 20} 0v{sh}z" fill="#6c6a68"/>'
        for x, sh in ((int(w * f), rng.randint(h // 10, h // 5)) for f in (0.18, 0.4, 0.6, 0.8))
    )
    return _ground(w, h, "#201c22") + stones


SCENES: dict[str, Scene] = {
    "wilds": _wilds,
    "forest": _forest,
    "ruins": _ruins,
    "bridge": _bridge,
    "cave": _cave,
    "village": _village,
    "swamp": _swamp,
    "keep": _keep,
    "crypt": _crypt,
}
TERRAINS = tuple(SCENES)
TIER_TERRAIN = {"tier1": "village", "tier2": "ruins", "tier3": "keep"}
SKY = {"cave": "#120f0c", "crypt": "#17121c", "swamp": "#1c2a28"}


def _sky(w: int, h: int, terrain: str) -> str:
    color = SKY.get(terrain, "#2a3350")
    return (
        f'<rect width="{w}" height="{round(h * HORIZON)}" fill="{color}" opacity="0.85"/>'
        f'<circle cx="{w * 0.82:.0f}" cy="{h * 0.2:.0f}" r="{h * 0.07:.0f}" '
        f'fill="{PALETTE["parchment"]}" opacity="0.35"/>'
    )


def scene_body(slug: str, size: Size, rng: random.Random) -> str:
    terrain = TIER_TERRAIN.get(slug, slug)
    draw = SCENES.get(terrain, _wilds)
    w, h = size
    return _sky(w, h, terrain) + draw(w, h, rng)


def banner_body(slug: str, size: Size, rng: random.Random) -> str:
    w, h = size
    caption = escape(slug.replace("tier", "Tier ").replace("-", " ").title())
    ribbon = (
        f'<rect x="{w * 0.3:.0f}" y="{h - 64}" width="{w * 0.4:.0f}" height="40" '
        f'fill="{PALETTE["ink"]}" '
        f'opacity="0.8" stroke="{PALETTE["gold_dim"]}" stroke-width="2"/>'
        f'<text x="{w // 2}" y="{h - 36}" text-anchor="middle" font-family="monospace" '
        f'font-size="24" '
        f'fill="{PALETTE["gold"]}">{caption}</text>'
    )
    return scene_body(slug, size, rng) + ribbon
