"""Vector glyphs (100 x 100 box) for placeholder icons: creature types, item categories, schools.

A glyph is a list of shapes drawn in one colour. Shape forms: ("p", d) stroked path, ("f", d)
filled path, ("c", cx, cy, r) stroked circle, ("d", cx, cy, r) filled circle, ("e", cx, cy, rx, ry)
filled ellipse, ("g", points) stroked polygon, ("r", x, y, w, h, rx) stroked rectangle, ("t", angle)
filled gear tooth. Unknown names fall back to a question-mark rhombus.

Public API: `creature_glyph`, `item_glyph`, `school_glyph`, `generic_glyph`.
"""

from collections.abc import Sequence

type Shape = tuple[str | float, ...]
type Glyph = Sequence[Shape]

LINE = 'fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"'


def _draw(shape: Shape, c: str, w: int) -> str:
    kind, *a = shape
    line = LINE.format(c=c, w=w)
    if kind == "p":
        return f'<path d="{a[0]}" {line}/>'
    if kind == "f":
        return f'<path d="{a[0]}" fill="{c}"/>'
    if kind == "c":
        return f'<circle cx="{a[0]}" cy="{a[1]}" r="{a[2]}" {line}/>'
    if kind == "d":
        return f'<circle cx="{a[0]}" cy="{a[1]}" r="{a[2]}" fill="{c}"/>'
    if kind == "e":
        return f'<ellipse cx="{a[0]}" cy="{a[1]}" rx="{a[2]}" ry="{a[3]}" fill="{c}"/>'
    if kind == "g":
        return f'<polygon points="{a[0]}" {line}/>'
    if kind == "r":
        return f'<rect x="{a[0]}" y="{a[1]}" width="{a[2]}" height="{a[3]}" rx="{a[4]}" {line}/>'
    return (
        f'<rect x="44" y="8" width="12" height="16" fill="{c}" transform="rotate({a[0]} 50 50)"/>'
    )


def _render(glyph: Glyph, c: str, w: int = 5) -> str:
    return "".join(_draw(shape, c, w) for shape in glyph)


GENERIC: Glyph = (
    ("g", "50,12 88,50 50,88 12,50"),
    ("p", "M40 40q0-12 10-12t10 10q0 8-10 14v6"),
    ("d", 50, 72, 3.5),
)
SKULL: Glyph = (
    ("p", "M24 52a26 26 0 1 1 52 0v10H66v10H34V62H24z"),
    ("d", 38, 50, 6),
    ("d", 62, 50, 6),
    ("f", "M50 58l-4 8h8z"),
)
HORNS: Glyph = (
    ("p", "M30 70q-18-8-14-40q10 14 24 20"),
    ("p", "M70 70q18-8 14-40q-10 14-24 20"),
    ("c", 50, 64, 16),
    ("p", "M42 62l6 4M58 62l-6 4"),
)
PAW: Glyph = (
    ("e", 50, 66, 18, 14),
    *(("e", x, y, 7, 9) for x, y in ((26, 44), (42, 30), (58, 30), (74, 44))),
)
DRAGON: Glyph = (
    ("p", "M12 62q10-30 38-22q-6-14 4-26q8 16 4 26q18 2 30 20q-14-4-24 0q-4 14-18 14q-18 0-34-12z"),
    ("d", 60, 42, 3),
)
HELM: Glyph = (
    ("p", "M24 60V44q0-26 26-26t26 26v16l-8 22H32z"),
    ("p", "M30 48h40M50 48v34"),
)
GEAR: Glyph = (
    *(("t", angle) for angle in range(0, 360, 45)),
    ("c", 50, 50, 24),
    ("c", 50, 50, 9),
)
FLAME: Glyph = (
    ("p", "M50 10q6 22 22 34q10 12 2 30q-10 14-24 14t-24-14q-8-18 4-32q6 12 14 8q-6-20 6-40z"),
)
LEAF: Glyph = (("p", "M20 80q-4-50 40-62q24 4 22 24q-6 40-52 42zM20 80l40-40"),)
EYE: Glyph = (
    ("p", "M8 50q42-46 84 0q-42 46-84 0z"),
    ("c", 50, 50, 14),
    ("d", 50, 50, 5),
)
WING_ORB: Glyph = (
    ("c", 50, 50, 18),
    ("p", "M32 50q-18-4-24-20q20 0 28 12M68 50q18-4 24-20q-20 0-28 12"),
)
DROP: Glyph = (("p", "M50 12q30 34 30 52a30 30 0 0 1-60 0q0-18 30-52z"),)
GIANT: Glyph = (("p", "M30 90V60l-8-24 14-10 8 12h12l8-12 14 10-8 24v30z"),)
SWIRL: Glyph = (
    ("p", "M50 50m0-6a6 6 0 1 1-6 6q0-16 16-16q22 0 22 22q0 28-32 28q-36 0-36-36q0-34 36-34"),
)
TREE: Glyph = (("p", "M50 90V60M50 60q-30 0-30-22q0-24 30-26q30 2 30 26q0 22-30 22z"),)
TENTACLE: Glyph = (
    ("c", 50, 34, 20),
    ("p", "M30 50q-14 20 0 38M50 54q-6 20 6 36M70 50q14 20 0 38"),
)
CREATURE_GLYPHS: dict[str, Glyph] = {
    "aberration": TENTACLE,
    "beast": PAW,
    "celestial": WING_ORB,
    "construct": GEAR,
    "dragon": DRAGON,
    "elemental": FLAME,
    "fey": LEAF,
    "fiend": HORNS,
    "giant": GIANT,
    "humanoid": HELM,
    "monstrosity": EYE,
    "ooze": DROP,
    "plant": TREE,
    "undead": SKULL,
}

SWORD: Glyph = (("p", "M78 14L40 52l8 8L86 22zM34 58l8 8M26 74l-8 8M40 74l-14 14"),)
ARMOR: Glyph = (("p", "M20 22l20-8q10 10 20 0l20 8-4 22-10 4v34H34V48l-10-4z"),)
BAG: Glyph = (
    ("p", "M36 18h28l-6 14q24 14 20 44q-2 12-28 12t-28-12q-4-30 20-44z"),
    ("p", "M38 32h24"),
)
HAMMER: Glyph = (("p", "M24 24h40v20H24zM44 44v44"), ("p", "M64 28l14-6v28l-14-6"))
FLASK: Glyph = (
    ("p", "M42 14h16M44 14v22L22 78q-4 12 10 12h36q14 0 10-12L56 36V14"),
    ("p", "M32 66h36"),
)
BUNDLE: Glyph = (
    ("r", 18, 38, 64, 40, 6),
    ("p", "M18 52h64M40 38v-12h20v12M50 52v10"),
)
KEY: Glyph = (("c", 32, 34, 16), ("p", "M44 46l38 38M68 70l8-8M58 60l8-8"))
SCROLL: Glyph = (
    ("p", "M26 20h46v52q0 12 10 12H34q-10 0-10-12V28q0-8 10-8zM38 36h26M38 50h26M38 64h18"),
)
ITEM_GLYPHS: dict[str, Glyph] = {
    "weapon": SWORD,
    "armor": ARMOR,
    "gear": BAG,
    "tool": HAMMER,
    "potion": FLASK,
    "supply": BUNDLE,
    "key": KEY,
    "scroll": SCROLL,
}

SHIELD: Glyph = (
    ("p", "M50 10l34 12v26q0 30-34 42Q16 78 16 48V22z"),
    ("p", "M50 26v46M30 44h40"),
)
PORTAL: Glyph = (("c", 50, 50, 24), ("c", 50, 50, 10))
HEART: Glyph = (
    ("p", "M50 84Q14 58 14 36q0-20 20-20q12 0 16 12q4-12 16-12q20 0 20 20Q86 58 50 84z"),
)
MOON: Glyph = (("p", "M62 12a38 38 0 1 0 26 56q-30 6-40-20q-6-20 14-36z"),)
BURST: Glyph = (("p", "M50 8l10 28 28-10-18 24 20 22-30-4-10 28-10-28-30 4 20-22-18-24 28 10z"),)
SCHOOL_GLYPHS: dict[str, Glyph] = {
    "abjuration": SHIELD,
    "conjuration": PORTAL,
    "divination": EYE,
    "enchantment": HEART,
    "evocation": BURST,
    "illusion": MOON,
    "necromancy": SKULL,
    "transmutation": SWIRL,
    "fire": FLAME,
    "acid": DROP,
    "poison": DROP,
    "cold": BURST,
    "frost": BURST,
    "lightning": BURST,
    "thunder": BURST,
    "radiant": WING_ORB,
    "force": PORTAL,
    "necrotic": SKULL,
    "psychic": EYE,
    "arcane": SWIRL,
    "nature": LEAF,
}


def generic_glyph(c: str) -> str:
    return _render(GENERIC, c, 6)


def creature_glyph(creature_type: str, c: str) -> str:
    return _render(CREATURE_GLYPHS.get(creature_type.lower(), GENERIC), c)


def item_glyph(category: str, c: str) -> str:
    return _render(ITEM_GLYPHS.get(category.lower(), GENERIC), c)


def school_glyph(school: str, c: str) -> str:
    return _render(SCHOOL_GLYPHS.get(school.lower(), GENERIC), c)
