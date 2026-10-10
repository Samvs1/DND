"""Image-generation prompts for manifest entries (Addendum A.4, B.3).

A prompt is the style bible prefix (docs/STYLE_BIBLE.md, block under "Prompt prefix"), then the
subject details taken from the data registries (race, class, creature type and CR, item category,
spell school and damage, condition, terrain; UI chrome art from `asset_ui`), then the per-kind
note ("Kind prompts" section).
Audio entries get a short sound brief instead (not an image). Prompts never name any game, studio
or real person.

Public API: `StyleBible`, `load_style_bible`, `build_prompt`, `build_subject`, `STYLE_BIBLE_PATH`.
"""

import functools
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aidm.data.class_defs import class_defs
from aidm.data.condition_defs import condition_defs
from aidm.data.item_catalogue import item_catalogue
from aidm.data.race_defs import race_defs
from aidm.data.spell_defs import spell_defs
from aidm.data.srd import srd
from aidm.data.zone_templates import zone_templates
from aidm.server.asset_keys import AUDIO_KINDS, AssetSpec, split_key
from aidm.server.asset_ui import ui_subject

STYLE_BIBLE_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "STYLE_BIBLE.md"
_PREFIX = re.compile(r"## Prompt prefix\s+```text\n(.*?)\n```", re.S)
_KIND = re.compile(r"^- `(\w+)`: (.+)$", re.M)
RACE_LOOKS = {
    "dragonborn": "a scaled draconic head, a short snout and a heavy tail",
    "dwarf": "stocky, braided beard, broad shoulders",
    "elf": "slender, pointed ears, graceful bearing",
    "gnome": "small and wiry, oversized curious eyes, tinkerer's tools",
    "half-elf": "human build with subtly pointed ears",
    "half-orc": "tall and heavy, grey-green skin, small lower tusks",
    "halfling": "small and nimble, bare feet, a friendly face",
    "human": "an ordinary human build and features",
    "tiefling": "curling horns, a slim tail, faintly red or violet skin",
}
TIER_MOODS = {
    "tier1": "a hopeful dawn over quiet outskirts and a country road",
    "tier2": "dusk light over deeper wilds and old ruins",
    "tier3": "a dark stronghold under storm light, embers in the air",
}
SCHOOL_LOOKS = {
    "acid": "bubbling green acid",
    "arcane": "swirling violet arcane runes",
    "cold": "icy cyan crystals",
    "fire": "ember-red flame",
    "force": "a violet force bolt",
    "frost": "icy cyan frost",
    "lightning": "a jagged yellow lightning bolt",
    "nature": "green leaves and vines",
    "necrotic": "sickly green withering shadow",
    "poison": "a green poison droplet",
    "radiant": "golden radiant light",
    "thunder": "a violet shockwave ring",
}
SOUND_BRIEFS = {
    "music.social": "a warm conversation bed, lute and soft hand drum, loopable, 2 to 3 minutes",
    "sfx.ui_click": "a soft wooden button click, 0.2 seconds",
    "sfx.dice_roll": "a handful of dice rattling on a wooden table, 1 second",
    "sfx.hit": "a short weapon hit on leather and flesh, 0.5 seconds",
    "sfx.miss": "a sword whooshing through air, 0.5 seconds",
    "sfx.crit": "a heavy, resonant weapon strike with a bright ring, 1 second",
    "sfx.spell_cast": "a rising magical shimmer ending in a soft burst, 1 second",
    "sfx.heal": "a gentle warm chime with a soft sparkle, 1 second",
    "sfx.level_up": "a short triumphant rising fanfare of three notes, 2 seconds",
    "sfx.door": "a heavy wooden door creaking open, 1.5 seconds",
    "sfx.coin": "a few gold coins clinking into a pouch, 0.7 seconds",
}


@dataclass(frozen=True)
class StyleBible:
    prefix: str
    kinds: dict[str, str]


@functools.cache
def load_style_bible(path: Path = STYLE_BIBLE_PATH) -> StyleBible:
    text = path.read_text(encoding="utf-8")
    match = _PREFIX.search(text)
    if match is None:
        raise ValueError(f"{path.name}: no prompt prefix block")
    kinds = text.split("## Kind prompts", 1)[-1].split("\n## ", 1)[0]
    return StyleBible(match.group(1).strip(), dict(_KIND.findall(kinds)))


def _words(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ")


def _damage_types(node: Any) -> list[str]:
    found: list[str] = []
    children: list[Any] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "damage_type" and isinstance(value, str):
                found.append(value)
            else:
                children.append(value)
    elif isinstance(node, list | tuple):
        children = list(node)
    for child in children:
        found += _damage_types(child)
    return list(dict.fromkeys(found))


def _monster(index: str) -> str:
    m = srd().monsters.find(index)
    if m is None:
        return _words(index)
    kind = f"{m.type} ({m.subtype})" if m.subtype else m.type
    return f"{m.name}, a {m.size.lower()} {kind} of challenge rating {m.challenge_rating:g}"


def _portrait(slug: str) -> str:
    group, _, rest = slug.partition(".")
    if group == "race":
        race, _, sex = rest.rpartition(".")
        r = race_defs().find(race)
        who = "female" if sex == "f" else "male"
        size = f", {r.size.lower()} size" if r is not None else ""
        name = r.name if r is not None else _words(race)
        look = RACE_LOOKS.get(race, "")
        return f"A {who} {name} adventurer{size}, {look}, in plain travelling clothes with a pack"
    if group in ("class", "icon"):
        c = class_defs().find(rest)
        name = c.name if c is not None else _words(rest)
        focus = " and a spellcaster's focus" if c is not None and c.spellcasting else ""
        face = "Head and shoulders face of a" if group == "icon" else "A"
        return f"{face} {name} adventurer with the gear of the class{focus}"
    who = _monster(rest)
    return f"{who}, shown as a person the party might meet, with props that tell what they do"


def _item(slug: str) -> str:
    item = item_catalogue().find(slug)
    if item is not None:
        return f"A {item.name.lower()} ({item.category.value}, tier {item.tier})"
    return f"A {_words(slug)} (a category icon: the typical object of that kind)"


# A spell whose damage-type look would draw the wrong picture (owner request 2026-10-10: Magic
# Missile came out as one violet bolt, the same as Eldritch Blast; SRD: "three glowing darts").
SPELL_LOOKS = {"magic-missile": "three small glowing violet darts of force flying side by side"}


def _spell(slug: str) -> str:
    if slug.startswith("school."):
        school = slug.partition(".")[2]
        return f"The {school} magic school emblem showing {SCHOOL_LOOKS.get(school, school)}"
    spell = srd().spells.find(slug)
    defn = spell_defs().find(slug)
    name = spell.name if spell is not None else _words(slug)
    school = spell.school.name.lower() if spell is not None else "magic"
    level = f"level {spell.level}" if spell is not None and spell.level else "cantrip"
    damage = _damage_types(defn.model_dump()) if defn is not None else []
    looks = SPELL_LOOKS.get(slug) or ", ".join(SCHOOL_LOOKS.get(d, d) for d in damage)
    return f"The spell {name} ({school}, {level}) shown as {looks or f'{school} magic'}"


def _condition(slug: str) -> str:
    cond = condition_defs().find(slug)
    name = cond.name if cond is not None else _words(slug)
    return f"The status condition {name} as a plain symbol"


def _place(slug: str) -> str:
    if slug in TIER_MOODS:
        return f"A regional vista: {TIER_MOODS[slug]}"
    terrain = zone_templates().find(slug)
    name = terrain.name if terrain is not None else _words(slug)
    parts = ", ".join(z.names[0].lower() for z in terrain.zones[:3]) if terrain else ""
    return f"The terrain {name.lower()}" + (f" with {parts}" if parts else "")


def _subject(spec: AssetSpec) -> str:
    kind, slug = split_key(spec.key)
    chrome = ui_subject(spec.key)
    if chrome is not None:
        return chrome
    builders: dict[str, Callable[[str], str]] = {
        "portrait": _portrait,
        "monster_token": _monster,
        "item_icon": _item,
        "spell_icon": _spell,
        "condition_icon": _condition,
    }
    return builders.get(kind, _place)(slug)


def build_subject(spec: AssetSpec) -> str:
    """The subject sentence of an image entry, from the data (used by the asset generator)."""
    return _subject(spec)


def build_prompt(spec: AssetSpec, bible: StyleBible | None = None) -> str:
    """The generation prompt for one manifest entry (a sound brief for audio kinds)."""
    if spec.kind in AUDIO_KINDS:
        brief = SOUND_BRIEFS.get(spec.key, _words(split_key(spec.key)[1]))
        return f"Audio brief (not an image): {brief}."
    style = bible if bible is not None else load_style_bible()
    note = style.kinds.get(spec.kind, "")
    size = f" Target size {spec.size[0]}x{spec.size[1]}." if spec.size else ""
    transparent = " Transparent background." if spec.transparent else ""
    return f"{style.prefix} Subject: {_subject(spec)}. {note}{size}{transparent}".strip()
