"""Seeded zone-map generation from terrain tags."""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.data.zone_templates import FALLBACK_TERRAIN, zone_templates
from aidm.rules.zone_gen import generate_zone_map
from aidm.rules.zones import zone_hops

TERRAINS = [t.index for t in zone_templates().all()]


def test_same_seed_and_tags_give_the_same_map() -> None:
    a = generate_zone_map(random.Random(7), ["forest"], zone_templates())
    b = generate_zone_map(random.Random(7), ["forest"], zone_templates())
    assert a == b
    seeds = {
        generate_zone_map(random.Random(s), ["forest"], zone_templates()).model_dump_json()
        for s in range(20)
    }
    assert len(seeds) > 5


def test_zones_come_from_the_requested_terrain() -> None:
    keys = {z.key for z in zone_templates().get("cave").zones}
    m = generate_zone_map(random.Random(3), ["Cave ", "nonsense"], zone_templates())
    assert {z.id for z in m.zones} <= keys
    assert all(e.feet == zone_templates().get("cave").hop_feet for e in m.edges)


def test_unknown_tags_fall_back_to_wilds() -> None:
    keys = {z.key for z in zone_templates().get(FALLBACK_TERRAIN).zones}
    m = generate_zone_map(random.Random(1), ["moonbase"], zone_templates())
    assert {z.id for z in m.zones} <= keys
    assert generate_zone_map(random.Random(1), [], zone_templates()) == m


def test_names_come_from_the_template_table() -> None:
    m = generate_zone_map(random.Random(11), ["keep"], zone_templates())
    by_key = {z.key: z for z in zone_templates().get("keep").zones}
    for zone in m.zones:
        assert zone.name in by_key[zone.id].names
        assert zone.surfaces == []


@settings(max_examples=150)
@given(
    seed=st.integers(0, 2**31),
    tags=st.lists(st.sampled_from([*TERRAINS, "unknown"]), max_size=3),
)
def test_generated_maps_are_connected_with_3_to_6_zones(seed: int, tags: list[str]) -> None:
    m = generate_zone_map(random.Random(seed), tags, zone_templates())
    assert 3 <= len(m.zones) <= 6
    first = m.zones[0].id
    for zone in m.zones:
        assert zone_hops(m, first, zone.id) >= 0  # every zone reachable (validator agrees)
    assert len({z.id for z in m.zones}) == len(m.zones)
