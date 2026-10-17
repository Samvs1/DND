"""Asset keys derived from the data registries (Addendum A.2): the single list behind the manifest.

`derive_specs(static_dir)` returns one `AssetSpec` per key: classes, races, NPC archetypes,
encounter monsters, item categories (plus catalogue items that already have v1 art), shipped
spells (plus school icons), conditions, terrains, music states and sfx names, plus the UI chrome
art of `asset_ui.UI_ART` (defeat scene, controller tab icons). Adding a data entry adds a key.
`v1` marks entries whose default file is existing owner art from the v1 project.

Public API: `AssetSpec`, `derive_specs`, `split_key`, `AUDIO_KINDS`.
"""

from dataclasses import dataclass
from pathlib import Path

from aidm.data.class_defs import class_defs
from aidm.data.condition_defs import condition_defs
from aidm.data.encounter_monsters import encounter_monsters
from aidm.data.item_catalogue import ItemCategory, item_catalogue
from aidm.data.race_defs import race_defs
from aidm.data.spell_defs import shipped_spell_ids
from aidm.data.srd import srd
from aidm.data.zone_templates import zone_templates
from aidm.server.asset_ui import UI_ART
from aidm.server.asset_zone_art import zone_art_files
from aidm.server.placeholders import placeholder_size
from aidm.server.sfxgen.names import DICE_SFX

AUDIO_KINDS = frozenset({"music", "sfx"})
MAX_ARCHETYPE_CR = 8.0
TOKEN_SIZE = (256, 256)
ICON_DIR = "img/icons"
ITEM_V1 = {
    "weapon": f"{ICON_DIR}/equipment/weapon.png",
    "armor": f"{ICON_DIR}/equipment/armor.png",
    "gear": f"{ICON_DIR}/items/item.png",
    "potion": f"{ICON_DIR}/items/potion_healing.png",
    "supply": f"{ICON_DIR}/items/camp_supplies.png",
    "key": f"{ICON_DIR}/items/key.png",
    "scroll": f"{ICON_DIR}/items/scroll.png",
}
CONDITION_V1 = {
    "bane": "baned",
    "mage-armor": "mage_armored",
    "shield-of-faith": "shielded",
    "hunters-mark": "marked",
}
SPELL_SCHOOLS = (
    "acid",
    "arcane",
    "cold",
    "fire",
    "force",
    "frost",
    "lightning",
    "nature",
    "necrotic",
    "poison",
    "radiant",
    "thunder",
)
MUSIC_STATES = ("exploration", "combat", "social", "victory", "defeat")
SFX_NAMES = (
    "ui_click",
    *(name for name in DICE_SFX if name not in ("hit", "miss", "crit")),  # M26.8 synthesised dice
    "hit",
    "miss",
    "crit",
    "spell_cast",
    "heal",
    "level_up",
    "door",
    "coin",
    "scribe_intro",
)
MUSIC_FILES = {
    "exploration": "ambient.mp3",
    "combat": "combat.mp3",
    "victory": "victory.mp3",
    "defeat": "defeat.mp3",
}
V1_AUDIO = {"music.victory", "music.defeat", "sfx.scribe_intro"}


@dataclass(frozen=True)
class AssetSpec:
    key: str
    kind: str
    file: str
    size: tuple[int, int] | None
    transparent: bool = False
    v1: bool = False
    hand: bool = False


def split_key(key: str) -> tuple[str, str]:
    """('monster_token', 'goblin') for 'monster_token.goblin'; the slug may contain dots."""
    kind, _, slug = key.partition(".")
    return kind, slug


def _spec(
    key: str, file: str, *, transparent: bool = False, v1: bool = False, hand: bool = False
) -> AssetSpec:
    kind = split_key(key)[0]
    size = None if kind in AUDIO_KINDS else placeholder_size(kind)
    return AssetSpec(key, kind, file, size, transparent, v1, hand)


def _portraits() -> list[AssetSpec]:
    out: list[AssetSpec] = []
    for cls in class_defs().all():
        out.append(
            _spec(f"portrait.class.{cls.index}", f"img/portraits/{cls.index}_cropped.png", v1=True)
        )
        icon = f"img/portraits/{cls.index.capitalize()}_p_icon.png"
        out.append(_spec(f"portrait.icon.{cls.index}", icon, transparent=True, v1=True))
    for race in race_defs().all():
        for sex in ("f", "m"):
            out.append(
                _spec(
                    f"portrait.race.{race.index}.{sex}",
                    f"img/portraits/race_{race.index}_{sex}.png",
                )
            )
    for name in ("scribe", "shopkeeper"):
        out.append(_spec(f"portrait.npc.{name}", f"img/portraits/{name}_cropped.png", v1=True))
    humanoids = sorted(
        m.index
        for m in srd().monsters.all()
        if m.type == "humanoid" and m.challenge_rating <= MAX_ARCHETYPE_CR
    )
    out += [_spec(f"portrait.npc.{a}", f"img/portraits/npc/{a}.png") for a in humanoids]
    return out


def _monsters() -> list[AssetSpec]:
    return [
        _spec(f"monster_token.{m.index}", f"img/monsters/{m.index}.png", transparent=True)
        for m in encounter_monsters().all()
    ]


def _items(static_dir: Path) -> list[AssetSpec]:
    out = []
    for category in ItemCategory:
        v1 = category.value in ITEM_V1
        file = ITEM_V1.get(category.value, f"{ICON_DIR}/items/{category.value}.png")
        out.append(_spec(f"item_icon.{category.value}", file, transparent=True, v1=v1))
    for extra in ("gold", "gem"):
        out.append(
            _spec(f"item_icon.{extra}", f"{ICON_DIR}/items/{extra}.png", transparent=True, v1=True)
        )
    for item in item_catalogue().all():
        file = f"{ICON_DIR}/equipment/{item.id}.png"
        gear = f"{ICON_DIR}/gear/{item.id}.png"  # M25: generated starting-gear icons
        if (static_dir / file).is_file():
            out.append(_spec(f"item_icon.{item.id}", file, transparent=True, v1=True))
        elif (static_dir / gear).is_file():
            out.append(_spec(f"item_icon.{item.id}", gear, transparent=True))
    return out


def _spells() -> list[AssetSpec]:
    out = [
        _spec(f"spell_icon.school.{s}", f"{ICON_DIR}/spells/{s}.png", transparent=True, v1=True)
        for s in SPELL_SCHOOLS
    ]
    out += [
        _spec(f"spell_icon.{i}", f"img/spells/{i}.png", transparent=True)
        for i in sorted(shipped_spell_ids())
    ]
    return out


def _conditions() -> list[AssetSpec]:
    out = []
    for cond in condition_defs().all():
        alias = CONDITION_V1.get(cond.index)
        stem = alias or cond.index.replace("-", "_")
        out.append(
            _spec(
                f"condition_icon.{cond.index}",
                f"{ICON_DIR}/conditions/{stem}.png",
                transparent=True,
                v1=True,
            )
        )
    return out


def _places() -> list[AssetSpec]:
    terrains = [t.index for t in zone_templates().all()]
    out = [_spec(f"zone_card.{t}", f"img/zones/{t}.png") for t in terrains]
    out += [
        _spec(f"region_banner.{t}", f"img/banners/{t}.png")
        for t in (*terrains, "tier1", "tier2", "tier3")
    ]
    return out


def _audio() -> list[AssetSpec]:
    out = []
    for state in MUSIC_STATES:
        file = f"audio/music/{MUSIC_FILES.get(state, state + '.mp3')}"
        out.append(
            _spec(f"music.{state}", file, v1=f"music.{state}" in V1_AUDIO or state in MUSIC_FILES)
        )
    for name in SFX_NAMES:
        file = "audio/scribe_intro.mp3" if name == "scribe_intro" else f"audio/sfx/{name}.mp3"
        out.append(_spec(f"sfx.{name}", file, v1=name == "scribe_intro"))
    return out


def _zone_art() -> list[AssetSpec]:
    """M21: hex tiles per zone type, zone marks and surface icons (`asset_zone_art`)."""
    return [_spec(key, file, transparent=clear) for key, file, clear in zone_art_files()]


def _ui() -> list[AssetSpec]:
    return [_spec(a.key, a.file, transparent=a.transparent, v1=a.v1, hand=a.hand) for a in UI_ART]


def derive_specs(static_dir: Path) -> list[AssetSpec]:
    """Every asset key the UI may ask for (sorted), with its default file under `static_dir`."""
    specs = [
        *_ui(),
        *_portraits(),
        *_monsters(),
        *_items(static_dir),
        *_spells(),
        *_conditions(),
        *_places(),
        *_zone_art(),
        *_audio(),
    ]
    return sorted(specs, key=lambda s: s.key)
