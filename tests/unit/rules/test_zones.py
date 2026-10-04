"""Zone geometry: movement cost, paths, reachability, range bands, high ground, cover."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aidm.models.zones import CoverLevel, RangeBand, Zone, ZoneEdge, ZoneMap
from aidm.rules.d20 import combine_adv
from aidm.rules.zones import (
    MELEE_BAND,
    ZoneError,
    cover_ac_bonus,
    high_ground_adv_counts,
    hop_cost,
    hops_for_range,
    range_band,
    reachable_zones,
    zone_hops,
    zone_neighbors,
    zone_path,
    zone_range_check,
)


def _map() -> ZoneMap:
    """bank -30- bridge -30- far ; bridge -15- tower(high, 3/4 cover) ; far -30- mire(difficult)."""
    return ZoneMap(
        zones=[
            Zone(id="bank", name="Near Bank"),
            Zone(id="bridge", name="Bridge"),
            Zone(id="far", name="Far Bank", cover=CoverLevel.HALF),
            Zone(id="tower", name="Tower", high_ground=True, cover=CoverLevel.THREE_QUARTERS),
            Zone(id="mire", name="Mire", difficult=True),
        ],
        edges=[
            ZoneEdge(a="bank", b="bridge", feet=30),
            ZoneEdge(a="bridge", b="far", feet=30),
            ZoneEdge(a="bridge", b="tower", feet=15),
            ZoneEdge(a="far", b="mire", feet=30),
        ],
    )


def test_map_validation_rejects_bad_graphs() -> None:
    a, b, c = (Zone(id=i, name=i) for i in "abc")
    with pytest.raises(ValidationError, match="not connected"):
        ZoneMap(zones=[a, b, c], edges=[ZoneEdge(a="a", b="b")])
    with pytest.raises(ValidationError, match="duplicate edge"):
        ZoneMap(zones=[a, b], edges=[ZoneEdge(a="a", b="b"), ZoneEdge(a="b", b="a")])
    with pytest.raises(ValidationError, match="unknown zone"):
        ZoneMap(zones=[a, b], edges=[ZoneEdge(a="a", b="x")])
    with pytest.raises(ValidationError, match="itself"):
        ZoneEdge(a="a", b="a")
    with pytest.raises(ValidationError, match="duplicate zone"):
        ZoneMap(zones=[a, a.model_copy()])
    assert ZoneMap(zones=[a]).has_zone("a")


def test_neighbors_and_hop_cost_double_into_difficult() -> None:
    m = _map()
    assert zone_neighbors(m, "bridge") == [("bank", 30), ("far", 30), ("tower", 15)]
    assert hop_cost(m, "far", "mire") == 60
    assert hop_cost(m, "mire", "far") == 30
    assert hop_cost(m, "bank", "far") is None
    with pytest.raises(ZoneError):
        hop_cost(m, "bank", "nowhere")


def test_cheapest_path_and_cost() -> None:
    m = _map()
    path = zone_path(m, "bank", "mire")
    assert path.zones == ("bank", "bridge", "far", "mire")
    assert path.feet == 30 + 30 + 60
    assert zone_path(m, "tower", "tower").feet == 0


def test_cheapest_path_prefers_lower_cost_over_fewer_hops() -> None:
    zones = [Zone(id=i, name=i) for i in ("a", "b", "c", "d")]
    edges = [
        ZoneEdge(a="a", b="d", feet=90),
        ZoneEdge(a="a", b="b", feet=15),
        ZoneEdge(a="b", b="c", feet=15),
        ZoneEdge(a="c", b="d", feet=15),
    ]
    m = ZoneMap(zones=zones, edges=edges)
    assert zone_path(m, "a", "d").zones == ("a", "b", "c", "d")
    assert zone_hops(m, "a", "d") == 1


def test_reachable_zones_with_remaining_movement() -> None:
    m = _map()
    assert reachable_zones(m, "bank", 30) == {"bank": 0, "bridge": 30}
    assert reachable_zones(m, "bank", 60) == {"bank": 0, "bridge": 30, "far": 60, "tower": 45}
    assert "mire" in reachable_zones(m, "bank", 120)
    assert reachable_zones(m, "bank", 0) == {"bank": 0}


def test_range_mapping_from_feet_to_hops() -> None:
    assert [hops_for_range(f) for f in (0, 5, 10, 15, 30, 60, 80, 120, 600)] == [
        0,
        0,
        0,
        1,
        1,
        1,
        2,
        2,
        2,
    ]
    assert range_band(5) == MELEE_BAND
    assert range_band(10) == MELEE_BAND  # reach weapons: same zone only
    assert range_band(30, 120) == RangeBand(normal_hops=1, max_hops=2)  # hand crossbow
    assert range_band(80, 320) == RangeBand(normal_hops=2, max_hops=2)  # shortbow
    assert range_band(20, 60) == RangeBand(normal_hops=1, max_hops=1)  # thrown dagger
    assert range_band(120) == RangeBand(normal_hops=2, max_hops=2)  # fire bolt


def test_range_check_long_range_and_out_of_range() -> None:
    m = _map()
    crossbow = range_band(30, 120)
    assert zone_range_check(m, "bank", "bank", MELEE_BAND).in_range
    assert not zone_range_check(m, "bank", "bridge", MELEE_BAND).in_range
    near = zone_range_check(m, "bank", "bridge", crossbow)
    assert (near.hops, near.in_range, near.long_range) == (1, True, False)
    far = zone_range_check(m, "bank", "far", crossbow)
    assert (far.hops, far.in_range, far.long_range) == (2, True, True)
    out = zone_range_check(m, "bank", "mire", crossbow)
    assert (out.hops, out.in_range, out.long_range) == (3, False, False)


def test_high_ground_counts_feed_combine_adv() -> None:
    m = _map()
    assert high_ground_adv_counts(m, "tower", "bridge", ranged=True) == (1, 0)
    assert high_ground_adv_counts(m, "tower", "bridge", ranged=False) == (1, 0)
    assert high_ground_adv_counts(m, "bridge", "tower", ranged=True) == (0, 1)
    assert high_ground_adv_counts(m, "bridge", "tower", ranged=False) == (0, 0)
    assert high_ground_adv_counts(m, "tower", "tower", ranged=True) == (0, 0)
    adv, dis = high_ground_adv_counts(m, "bridge", "tower", ranged=True)
    assert combine_adv(adv + 1, dis).value == "normal"  # another advantage source cancels


def test_cover_applies_to_ranged_attacks_from_another_zone() -> None:
    m = _map()
    assert cover_ac_bonus(m, "bridge", "far", ranged=True) == 2
    assert cover_ac_bonus(m, "bridge", "tower", ranged=True) == 5
    assert cover_ac_bonus(m, "tower", "tower", ranged=True) == 0
    assert cover_ac_bonus(m, "bridge", "far", ranged=False) == 0
    assert cover_ac_bonus(m, "far", "bank", ranged=True) == 0
