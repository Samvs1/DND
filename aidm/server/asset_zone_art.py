"""Art keys of the hex battle map (M21, owner: hexes that fit into each other, icons for
cover, rough ground and the like, new art per zone type).

- `zone_hex.<zone key>` (img/zones/hex/<key>.png, full bleed): the ground of one zone type from
  almost straight above; the screen clips it to a hex (js/combat/board.js), with the terrain's
  zone card as the fallback while it is a placeholder. One per zone template key
  (data/bg3/zone_templates.json).
- `zone_icon.<mark>` (img/icons/zones/<mark>.png, transparent): the marks of a zone
  (`ZONE_MARKS`).
- `surface_icon.<surface>` (img/icons/surfaces/<surface>.png, transparent): one per surface in
  data/bg3/surfaces.json.
Subjects come from the data (zone names, terrain, cover / high ground / rough flags, surface
names) plus the hand-written looks below. Data only: `aidm.server.asset_keys` builds the specs
and `aidm.server.asset_prompts` the prompts.

Public API: `ZONE_MARKS`, `SURFACE_LOOKS`, `zone_art_files() -> list[(key, file, transparent)]`,
`zone_hex_subject(slug)`, `zone_icon_subject(slug)`, `surface_icon_subject(slug)`.
"""

from aidm.data.surface_defs import surface_defs
from aidm.data.zone_templates import zone_templates

ZONE_MARKS = {
    "cover-half": (
        "Half cover: a low broken stone wall about waist high with a round wooden shield "
        "propped against it"
    ),
    "cover-three-quarters": (
        "Three-quarters cover: a tall stone wall with a narrow arrow slit and a shield leaning "
        "on it, tall enough to hide almost all of whoever stands behind it"
    ),
    "high-ground": (
        "High ground: a steep rocky crag with a small pennant flag planted on its summit"
    ),
    "rough": "Rough ground: a tangle of thorny brambles, loose stones and sticky mud",
    "dark": "Dark place: a pool of deep shadow with faint violet-edged wisps and no light in it",
    "lit": "Lit place: a small warm torch flame with a soft orange glow around it",
    "darkvision": "Darkvision: a single watchful eye with a pale glowing iris seen in the dark",
}
SURFACE_LOOKS = {
    "fire": "a burning patch of ground with bright orange flames",
    "oil": "a dark glossy pool of spilled lamp oil",
    "rubble": "a heap of broken stones and debris",
    "grease": "a slick yellowish puddle of grease with a slippery sheen",
    "water": "a shallow puddle of clear water with ripples",
    "ice": "a patch of slippery pale-blue ice with cracks",
    "poison-cloud": "a drifting cloud of sickly green poison gas",
    "steam": "a billowing white cloud of hot steam",
    "web": "a thick sticky spider web strung low across the ground",
    "fog": "a low bank of grey-white fog",
    "darkness": "a pool of unnatural black darkness with faint violet edges",
    "stinking-cloud": "a roiling yellow-green cloud of foul gas",
    "sleet-storm": "a small grey cloud pouring sleet and icy rain",
    "silence": "a hushed pale-blue sphere of stillness around a small cracked bell",
    "spike-growth": "sharp thorny spikes and twisted roots bursting from the ground",
    "spirit-guardians": "a ring of glowing golden spectral guardian spirits",
}
_COVER = {
    "half": "with low walls, rocks or debris to crouch behind",
    "three_quarters": "with tall walls or thick cover that hides most of a person",
}


def zone_art_files() -> list[tuple[str, str, bool]]:
    keys = sorted({z.key for t in zone_templates().all() for z in t.zones})
    out = [(f"zone_hex.{k}", f"img/zones/hex/{k}.png", False) for k in keys]
    out += [(f"zone_icon.{m}", f"img/icons/zones/{m}.png", True) for m in ZONE_MARKS]
    out += [
        (f"surface_icon.{s.index}", f"img/icons/surfaces/{s.index}.png", True)
        for s in surface_defs().all()
    ]
    return out


def zone_hex_subject(slug: str) -> str:
    for terrain in zone_templates().all():
        for zone in terrain.zones:
            if zone.key != slug:
                continue
            names = " or ".join(zone.names[:2])
            details = [_COVER[zone.cover]] if zone.cover in _COVER else []
            if zone.high_ground:
                details.append("a raised rise of higher ground")
            if zone.difficult:
                details.append("tangled, broken or boggy ground that is hard to cross")
            extra = f", {', '.join(details)}" if details else ""
            return f"The ground of a place called {names} in {terrain.name.lower()}{extra}"
    return f"The ground of {slug.replace('_', ' ')}"


def zone_icon_subject(slug: str) -> str:
    return ZONE_MARKS.get(slug, slug.replace("-", " "))


def surface_icon_subject(slug: str) -> str:
    surface = surface_defs().find(slug)
    name = surface.name if surface is not None else slug.replace("-", " ")
    look = SURFACE_LOOKS.get(slug, name.lower())
    return f"The surface {name}: {look}"
