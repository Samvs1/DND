"""Hex battle maps (M21, owner: "hexagonal grids that fit into each other so it's clear which zone
is next to which one"): generated maps link exactly the touching hexes; old saves get a fit."""

import random

import pytest

from aidm.data.zone_templates import zone_templates
from aidm.models.zones import HexCoord, Zone, ZoneEdge, ZoneMap
from aidm.rules.hex_layout import hex_layout, touching
from aidm.rules.zone_gen import MAX_HEX_ROWS, generate_zone_map


def _pairs(zone_map: ZoneMap) -> set[frozenset[str]]:
    return {e.key() for e in zone_map.edges}


def _touching_pairs(layout: dict[str, tuple[int, int]]) -> set[frozenset[str]]:
    ids = sorted(layout)
    return {
        frozenset((a, b))
        for i, a in enumerate(ids)
        for b in ids[i + 1 :]
        if touching(layout[a], layout[b])
    }


def test_generated_maps_link_exactly_the_touching_hexes() -> None:
    terrains = zone_templates()
    for terrain in terrains.all():
        for seed in range(40):
            zone_map = generate_zone_map(random.Random(seed), [terrain.index], terrains)
            layout = hex_layout(zone_map)
            assert all(z.hex is not None for z in zone_map.zones)
            assert 3 <= len(zone_map.zones) <= 6
            assert len(set(layout.values())) == len(layout)
            assert _pairs(zone_map) == _touching_pairs(layout), (terrain.index, seed)
            rows = [r for _, r in layout.values()]
            assert max(rows) - min(rows) + 1 <= MAX_HEX_ROWS
            assert {e.feet for e in zone_map.edges} == {terrain.hop_feet}


def test_same_seed_same_hex_map() -> None:
    first = generate_zone_map(random.Random(11), ["forest"], zone_templates())
    again = generate_zone_map(random.Random(11), ["forest"], zone_templates())
    assert first == again


def _old_map(ids: str, links: list[str]) -> ZoneMap:
    zones = [Zone(id=i, name=i.upper()) for i in ids]
    return ZoneMap(zones=zones, edges=[ZoneEdge(a=p[0], b=p[1]) for p in links])


@pytest.mark.parametrize(
    ("ids", "links"),
    [
        ("abc", ["ab", "bc"]),  # a chain: a and c must not touch
        ("abc", ["ab", "bc", "ac"]),  # a triangle
        ("abcd", ["ab", "ac", "ad"]),  # a star
        ("abcdef", ["ab", "bc", "cd", "de", "ef"]),  # a long chain
    ],
)
def test_old_saves_get_an_exact_fit_when_one_exists(ids: str, links: list[str]) -> None:
    zone_map = _old_map(ids, links)
    layout = hex_layout(zone_map)
    assert set(layout) == set(ids) and len(set(layout.values())) == len(ids)
    assert _touching_pairs(layout) == _pairs(zone_map)


def test_old_save_that_cannot_fit_still_places_every_zone() -> None:
    four = _old_map("abcd", ["ab", "ac", "ad", "bc", "bd", "cd"])  # no four hexes all touch
    layout = hex_layout(four)
    assert set(layout) == set("abcd") and len(set(layout.values())) == 4


def test_stored_hexes_are_used_and_must_be_distinct() -> None:
    zones = [
        Zone(id="a", name="A", hex=HexCoord(q=0, r=0)),
        Zone(id="b", name="B", hex=HexCoord(q=1, r=0)),
    ]
    assert hex_layout(ZoneMap(zones=zones, edges=[ZoneEdge(a="a", b="b")])) == {
        "a": (0, 0),
        "b": (1, 0),
    }
    clash = [
        Zone(id="a", name="A", hex=HexCoord(q=0, r=0)),
        Zone(id="b", name="B", hex=HexCoord(q=0, r=0)),
    ]
    with pytest.raises(ValueError, match="share a hex"):
        ZoneMap(zones=clash, edges=[ZoneEdge(a="a", b="b")])
