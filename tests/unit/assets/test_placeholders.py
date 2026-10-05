"""Placeholder SVG generators: deterministic, correct aspect, marked, never raise (A1)."""

import xml.etree.ElementTree as ET

import pytest

from aidm.server.placeholders import PLACEHOLDER_KINDS, SIZES, render_placeholder

SAMPLES = {
    "portrait": ["class.fighter", "race.elf.f", "race.dwarf.m", "npc.noble"],
    "monster_token": ["goblin", "adult-red-dragon"],
    "item_icon": ["weapon", "potion", "longsword"],
    "spell_icon": ["fire-bolt", "school.fire"],
    "condition_icon": ["poisoned", "mage-armor"],
    "zone_card": ["forest", "crypt", "tier1"],
    "region_banner": ["swamp", "tier3"],
}
META = {"creature_type": "dragon", "cr": "10"}


def _all() -> list[tuple[str, str]]:
    return [(kind, slug) for kind, slugs in SAMPLES.items() for slug in slugs]


def test_every_kind_is_sampled() -> None:
    assert set(SAMPLES) == set(PLACEHOLDER_KINDS) == set(SIZES)


@pytest.mark.parametrize(("kind", "slug"), _all())
def test_placeholder_is_deterministic_valid_and_marked(kind: str, slug: str) -> None:
    first = render_placeholder(kind, slug, META)
    assert first == render_placeholder(kind, slug, META)
    root = ET.fromstring(first)
    width, height = SIZES[kind]
    assert root.get("viewBox") == f"0 0 {width} {height}"
    assert (root.get("width"), root.get("height")) == (str(width), str(height))
    assert 'class="placeholder-mark"' in first


def test_different_keys_draw_differently() -> None:
    a = render_placeholder("monster_token", "goblin", {"creature_type": "humanoid"})
    b = render_placeholder("monster_token", "wolf", {"creature_type": "beast"})
    assert a != b


def test_race_features_show_in_the_silhouette() -> None:
    human = render_placeholder("portrait", "race.human.m")
    elf = render_placeholder("portrait", "race.elf.m")
    tiefling = render_placeholder("portrait", "race.tiefling.m")
    assert len({human, elf, tiefling}) == 3
    assert elf.count("<polygon") > human.count("<polygon")


def test_class_tint_differs_per_class() -> None:
    fighter = render_placeholder("portrait", "class.fighter")
    wizard = render_placeholder("portrait", "class.wizard")
    assert "#8a4b34" in fighter and "#3f64a0" in wizard


def test_monster_token_shows_cr_badge() -> None:
    meta = {"creature_type": "humanoid", "cr": "0.25"}
    assert ">1/4<" in render_placeholder("monster_token", "goblin", meta)


@pytest.mark.parametrize("kind", [*PLACEHOLDER_KINDS, "unknown", ""])
@pytest.mark.parametrize("slug", ["", "<>&\"'", "a" * 500, "x.y.z.w", "é中"])
def test_placeholder_never_raises_and_is_valid_xml(kind: str, slug: str) -> None:
    svg = render_placeholder(kind, slug, {"cr": "not-a-number", "creature_type": "?"})
    assert ET.fromstring(svg).tag.endswith("svg")
