"""Portrait placeholders: a head-and-shoulders silhouette tinted by class, with race features.

Features: pointed ears (elf, half-elf), horns (tiefling, dragonborn), beard (dwarf men), tusks
(half-orc), long hair (women), a smaller figure (halfling, gnome). NPC archetypes get a seeded tint.

Public API: `portrait_body`.
"""

import random

from aidm.server.placeholder_art import PALETTE, pick_hue
from aidm.server.placeholder_glyphs import item_glyph

CLASS_TINTS = {
    "fighter": "#8a4b34",
    "cleric": "#b49a52",
    "ranger": "#47703c",
    "rogue": "#505a66",
    "warlock": "#6d478f",
    "wizard": "#3f64a0",
}
CLASS_EMBLEMS = {
    "fighter": "weapon",
    "rogue": "weapon",
    "ranger": "weapon",
    "cleric": "armor",
    "warlock": "scroll",
    "wizard": "scroll",
}
RACE_TINT = "#6b5a46"
POINTY_EARS = {"elf", "half-elf", "high-elf"}
HORNED = {"tiefling", "dragonborn"}
BEARDED = {"dwarf", "hill-dwarf"}
SMALL = {"halfling", "gnome", "lightfoot-halfling", "rock-gnome"}
CX = 256


def _pt(x: float, y: float) -> str:
    return f"{x:.0f},{y:.0f}"


def _ears(head_y: float, s: float) -> str:
    out = []
    for sign in (-1, 1):
        pts = (
            _pt(CX + sign * 50 * s, head_y - 10 * s),
            _pt(CX + sign * 108 * s, head_y - 40 * s),
            _pt(CX + sign * 48 * s, head_y + 30 * s),
        )
        out.append(f'<polygon points="{" ".join(pts)}" fill="{PALETTE["ink"]}"/>')
    return "".join(out)


def _horns(head_y: float, s: float) -> str:
    out = []
    for sign in (-1, 1):
        d = f"M{CX + sign * 30 * s:.0f} {head_y - 50 * s:.0f}q{sign * 40 * s:.0f} {-70 * s:.0f} "
        d += f"{sign * 76 * s:.0f} {-34 * s:.0f}"
        width = f"{14 * s:.0f}"
        out.append(
            f'<path d="{d}" fill="none" stroke="{PALETTE["ink"]}" '
            f'stroke-width="{width}" stroke-linecap="round"/>'
        )
    return "".join(out)


def _beard(head_y: float, s: float) -> str:
    d = f"M{CX - 46 * s:.0f} {head_y + 6 * s:.0f}q{46 * s:.0f} {120 * s:.0f} {92 * s:.0f} 0z"
    return f'<path d="{d}" fill="{PALETTE["ink"]}" opacity="0.85"/>'


def _tusks(head_y: float, s: float) -> str:
    out = []
    for sign in (-1, 1):
        pts = (
            _pt(CX + sign * 14 * s, head_y + 34 * s),
            _pt(CX + sign * 22 * s, head_y + 12 * s),
            _pt(CX + sign * 30 * s, head_y + 34 * s),
        )
        out.append(f'<polygon points="{" ".join(pts)}" fill="#d9ceb0"/>')
    return "".join(out)


def _hair(head_y: float, s: float) -> str:
    left, right = CX - 62 * s, CX + 62 * s
    d = f"M{left:.0f} {head_y:.0f}q-10 {110 * s:.0f} {18 * s:.0f} {170 * s:.0f}"
    d += f"h{20 * s:.0f}V{head_y + 20 * s:.0f}z"
    mirror = f"M{right:.0f} {head_y:.0f}q10 {110 * s:.0f} {-18 * s:.0f} {170 * s:.0f}"
    mirror += f"h{-20 * s:.0f}V{head_y + 20 * s:.0f}z"
    return f'<path d="{d}{mirror}" fill="{PALETTE["ink"]}" opacity="0.8"/>'


def _features(race: str, female: bool, head_y: float, s: float) -> str:
    out = []
    if race in POINTY_EARS:
        out.append(_ears(head_y, s))
    if race in HORNED:
        out.append(_horns(head_y, s))
    if race in BEARDED and not female:
        out.append(_beard(head_y, s))
    if race == "half-orc":
        out.append(_tusks(head_y, s))
    if female:
        out.append(_hair(head_y, s))
    return "".join(out)


def _figure(tint: str, race: str, female: bool) -> str:
    s = 0.82 if race in SMALL else 1.0
    head_y = 200 + (24 if race in SMALL else 0)
    top = head_y + 92 * s
    x0, x1 = CX - 190 * s, CX + 190 * s
    shoulders = f"M{x0:.0f} 512Q{x0:.0f} {top:.0f} {CX} {top:.0f}Q{x1:.0f} {top:.0f} {x1:.0f} 512z"
    neck = (CX - 22 * s, head_y + 40 * s, 44 * s)
    body = (
        f'<path d="{shoulders}" fill="{tint}"/>'
        f'<rect x="{neck[0]:.0f}" y="{neck[1]:.0f}" width="{neck[2]:.0f}" height="60" '
        f'fill="{tint}"/>'
        f'<circle cx="{CX}" cy="{head_y}" r="{58 * s:.0f}" fill="{tint}"/>'
    )
    return body + _features(race, female, head_y, s)


def portrait_body(slug: str, rng: random.Random) -> str:
    """SVG body for `class.<c>`, `race.<r>.<f|m>` or an NPC slug (any other slug)."""
    parts = [p for p in slug.split(".") if p]
    race, female, tint, emblem = "human", rng.random() < 0.5, pick_hue(rng, lightness=0.36), ""
    if parts[:1] == ["class"] and len(parts) > 1:
        tint = CLASS_TINTS.get(parts[1], tint)
        glyph = item_glyph(CLASS_EMBLEMS.get(parts[1], "scroll"), PALETTE["parchment"])
        emblem = f'<g transform="translate(222 414) scale(0.6)" opacity="0.85">{glyph}</g>'
    elif parts[:1] == ["race"] and len(parts) > 1:
        race, female, tint = parts[1], parts[2:3] == ["f"], RACE_TINT
    return _figure(tint, race, female) + emblem
