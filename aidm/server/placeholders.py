"""Deterministic SVG placeholders for missing art (Addendum A.3). Pure: no I/O, never raises.

`render_placeholder(kind, slug, meta)` returns an SVG document for any kind and slug. The same
arguments always give the same text (seeded by the key hash). Each picture carries a small corner
mark so a placeholder is never mistaken for real art. `meta` carries optional data facts the caller
looked up (`creature_type`, `cr`, `school`, `category`); art that needs none works from the slug.

Slugs: portrait `class.<c>` | `race.<r>.<f|m>` | `npc.<archetype>`; monster_token `<id>`;
item_icon `<category|id>`; spell_icon `<id>` | `school.<name>`; condition_icon `<id>`;
zone_card `<terrain>`; region_banner `<terrain>` | `tier<n>`.

Public API: `render_placeholder`, `PLACEHOLDER_KINDS`, `placeholder_size`.
"""

from collections.abc import Callable, Mapping

from aidm.server.placeholder_art import (
    PALETTE,
    Size,
    escape,
    initials,
    pick_hue,
    seeded,
    svg_document,
)
from aidm.server.placeholder_glyphs import creature_glyph, generic_glyph, item_glyph, school_glyph
from aidm.server.placeholder_portraits import portrait_body
from aidm.server.placeholder_scenes import banner_body, scene_body

type Meta = Mapping[str, str]

SIZES: dict[str, Size] = {
    "portrait": (512, 512),
    "monster_token": (256, 256),
    "item_icon": (128, 128),
    "spell_icon": (128, 128),
    "condition_icon": (128, 128),
    "zone_card": (640, 360),
    "region_banner": (1024, 256),
}
SCHOOL_TINTS = {
    "abjuration": "#4f7fb0",
    "conjuration": "#8a5fb0",
    "divination": "#58a0a0",
    "enchantment": "#b05f86",
    "evocation": "#c0623a",
    "illusion": "#7a7ac0",
    "necromancy": "#5c8a56",
    "transmutation": "#b09a3a",
    "fire": "#c0623a",
    "acid": "#7fa83a",
    "poison": "#5c9a46",
    "frost": "#6aa8c8",
    "cold": "#6aa8c8",
    "lightning": "#d0c040",
    "thunder": "#8a8ac0",
    "radiant": "#e0c870",
    "force": "#9a6ac0",
    "necrotic": "#5a7a50",
    "arcane": "#6a7ac8",
    "nature": "#4f8a3b",
}


def placeholder_size(kind: str) -> Size:
    return SIZES.get(kind, (256, 256))


def _label(kind: str, slug: str) -> str:
    return f"Placeholder {kind.replace('_', ' ')}: {slug.replace('.', ' ').replace('-', ' ')}"


def _parts(slug: str) -> list[str]:
    return [p for p in slug.split(".") if p]


def _portrait(slug: str, meta: Meta) -> str:
    body = portrait_body(slug, seeded("portrait", slug))
    return svg_document(SIZES["portrait"], _label("portrait", slug), body, base=PALETTE["stone2"])


def _cr_text(cr: str) -> str:
    return (
        {"0.125": "1/8", "0.25": "1/4", "0.5": "1/2"}.get(cr, cr.removesuffix(".0")) if cr else "?"
    )


def _monster_token(slug: str, meta: Meta) -> str:
    rng = seeded("monster_token", slug)
    rim = pick_hue(rng, lightness=0.38, sat=0.45)
    glyph = creature_glyph(meta.get("creature_type", ""), PALETTE["parchment"])
    body = (
        f'<circle cx="128" cy="128" r="110" fill="{PALETTE["stone2"]}" stroke="{rim}" '
        f'stroke-width="10"/>'
        f'<circle cx="128" cy="128" r="94" fill="none" stroke="{PALETTE["gold_dim"]}" '
        f'stroke-width="2"/>'
        f'<g transform="translate(48 40) scale(1.6)">{glyph}</g>'
        f'<circle cx="198" cy="198" r="30" fill="{PALETTE["ink"]}" '
        f'stroke="{PALETTE["gold"]}" stroke-width="3"/>'
        f'<text x="198" y="206" text-anchor="middle" font-family="monospace" font-size="22" '
        f'fill="{PALETTE["gold"]}">{escape(_cr_text(meta.get("cr", "")))}</text>'
    )
    return svg_document(SIZES["monster_token"], _label("monster_token", slug), body)


def _framed_glyph(kind: str, slug: str, glyph: str, tint: str) -> str:
    body = (
        f'<circle cx="64" cy="64" r="52" fill="{PALETTE["stone2"]}" stroke="{tint}" '
        f'stroke-width="4"/>'
        f'<g transform="translate(24 24) scale(0.8)">{glyph}</g>'
    )
    return svg_document(SIZES[kind], _label(kind, slug), body)


def _item_icon(slug: str, meta: Meta) -> str:
    category = meta.get("category") or slug
    rng = seeded("item_icon", slug)
    return _framed_glyph(
        "item_icon", slug, item_glyph(category, PALETTE["parchment"]), pick_hue(rng, lightness=0.45)
    )


def _spell_icon(slug: str, meta: Meta) -> str:
    school = meta.get("school") or (_parts(slug)[1] if slug.startswith("school.") else "")
    tint = SCHOOL_TINTS.get(school, pick_hue(seeded("spell_icon", slug), lightness=0.5, sat=0.4))
    return _framed_glyph("spell_icon", slug, school_glyph(school, tint), tint)


def _condition_icon(slug: str, meta: Meta) -> str:
    rng = seeded("condition_icon", slug)
    tint = pick_hue(rng, lightness=0.5, sat=0.4)
    letter = escape(initials(slug))
    body = (
        f'<circle cx="64" cy="64" r="52" fill="{PALETTE["stone2"]}" stroke="{tint}" '
        f'stroke-width="5"/>'
        f'<text x="64" y="86" text-anchor="middle" font-family="monospace" font-size="64" '
        f'font-weight="bold" fill="{tint}">{letter}</text>'
    )
    return svg_document(SIZES["condition_icon"], _label("condition_icon", slug), body)


def _zone_card(slug: str, meta: Meta) -> str:
    size = SIZES["zone_card"]
    return svg_document(
        size, _label("zone_card", slug), scene_body(slug, size, seeded("zone_card", slug))
    )


def _region_banner(slug: str, meta: Meta) -> str:
    size = SIZES["region_banner"]
    return svg_document(
        size, _label("region_banner", slug), banner_body(slug, size, seeded("region_banner", slug))
    )


def _generic(slug: str, meta: Meta) -> str:
    body = f'<g transform="translate(36 36) scale(1.84)">{generic_glyph(PALETTE["muted"])}</g>'
    return svg_document((256, 256), _label("asset", slug), body)


RENDERERS: dict[str, Callable[[str, Meta], str]] = {
    "portrait": _portrait,
    "monster_token": _monster_token,
    "item_icon": _item_icon,
    "spell_icon": _spell_icon,
    "condition_icon": _condition_icon,
    "zone_card": _zone_card,
    "region_banner": _region_banner,
}
PLACEHOLDER_KINDS = tuple(RENDERERS)


def render_placeholder(kind: str, slug: str, meta: Meta | None = None) -> str:
    """The SVG text for (kind, slug). Unknown kinds and drawing errors give the generic one."""
    facts: Meta = meta or {}
    try:
        return RENDERERS.get(kind, _generic)(slug, facts)
    except Exception:
        return _generic(slug, {})
