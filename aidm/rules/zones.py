"""Zone geometry: movement, paths, range bands, high ground and cover (SPEC 7.2, 7.3).

All distance questions are answered from the `ZoneMap` graph; there is no grid.

Movement: entering an adjacent zone costs the edge's `feet`, doubled when the zone entered is
`difficult` (SRD 5.1 Difficult Terrain: every foot costs 1 extra foot). Moving inside a zone is
free. Paths are cheapest-cost (Dijkstra; ties broken by zone id, so results are deterministic).

Range bands (one mapping for weapons and spells, `hops_for_range`):
- range <= 10 ft (melee, touch, self, and 10-ft reach weapons): the SAME zone only (0 hops);
- range <= 60 ft: same or adjacent zone (1 hop);
- range > 60 ft: up to 2 hops.
A weapon with a long range reaches `hops_for_range(long)` hops; hops beyond its normal band are
long range (disadvantage source). E.g. hand crossbow 30/120: 1 hop normal, 2 hops at
disadvantage; shortbow 80/320: 2 hops normal; dagger thrown 20/60: 1 hop. Nothing reaches 3 hops.

High ground (BG3): an attacker in a `high_ground` zone attacking a target in a zone without it
gains one advantage source; a ranged attack from a zone without high ground at a target on high
ground gets one disadvantage source. Same-zone attacks never change (both share the zone).
Cover: a ranged attack from ANOTHER zone into a zone with cover adds +2 (half) / +5 (three
quarters) to the target's AC (SRD 5.1 Cover). Attacks inside the zone ignore it.

Public API: `zone_neighbors(zone_map, zone_id) -> list[(zone_id, feet)]` (cost to ENTER each),
`hop_cost(zone_map, a, b) -> int | None`, `zone_path(zone_map, start, goal) -> ZonePath`,
`reachable_zones(zone_map, start, movement_feet) -> dict[zone_id, feet]`,
`zone_hops(zone_map, a, b) -> int`, `hops_for_range(feet) -> int`,
`range_band(normal_feet, long_feet=None) -> RangeBand`, `MELEE_BAND`,
`zone_range_check(zone_map, a, b, band) -> RangeCheck`,
`high_ground_adv_counts(zone_map, attacker_zone, target_zone, *, ranged) -> (adv, dis)`,
`cover_ac_bonus(zone_map, attacker_zone, target_zone, *, ranged) -> int`, `COVER_AC`.
Unknown zone ids raise `ZoneError` (an engine bug or a tool input the caller validates first).
"""

import heapq

from aidm.models.zones import CoverLevel, RangeBand, RangeCheck, ZoneMap, ZonePath

MELEE_RANGE_FEET = 10
NEAR_RANGE_FEET = 60
MAX_RANGE_HOPS = 2
COVER_AC: dict[CoverLevel, int] = {
    CoverLevel.NONE: 0,
    CoverLevel.HALF: 2,
    CoverLevel.THREE_QUARTERS: 5,
}
MELEE_BAND = RangeBand(normal_hops=0, max_hops=0)


class ZoneError(ValueError):
    """A zone id that is not on the map."""


def _require(zone_map: ZoneMap, *zone_ids: str) -> None:
    for zone_id in zone_ids:
        if not zone_map.has_zone(zone_id):
            raise ZoneError(f"unknown zone {zone_id!r}")


def zone_neighbors(zone_map: ZoneMap, zone_id: str) -> list[tuple[str, int]]:
    _require(zone_map, zone_id)
    found: list[tuple[str, int]] = []
    for edge in zone_map.edges:
        if zone_id in (edge.a, edge.b):
            other = edge.b if zone_id == edge.a else edge.a
            factor = 2 if zone_map.zone(other).difficult else 1
            found.append((other, edge.feet * factor))
    return sorted(found)


def hop_cost(zone_map: ZoneMap, a: str, b: str) -> int | None:
    _require(zone_map, b)
    return dict(zone_neighbors(zone_map, a)).get(b)


def _dijkstra(zone_map: ZoneMap, start: str) -> tuple[dict[str, int], dict[str, str]]:
    _require(zone_map, start)
    best: dict[str, int] = {start: 0}
    prev: dict[str, str] = {}
    done: set[str] = set()
    heap: list[tuple[int, str]] = [(0, start)]
    while heap:
        cost, here = heapq.heappop(heap)
        if here in done:
            continue
        done.add(here)
        for other, step in zone_neighbors(zone_map, here):
            total = cost + step
            if other not in best or total < best[other]:
                best[other] = total
                prev[other] = here
                heapq.heappush(heap, (total, other))
    return best, prev


def zone_path(zone_map: ZoneMap, start: str, goal: str) -> ZonePath:
    _require(zone_map, goal)
    best, prev = _dijkstra(zone_map, start)
    route = [goal]
    while route[-1] != start:
        route.append(prev[route[-1]])
    return ZonePath(zones=tuple(reversed(route)), feet=best[goal])


def reachable_zones(zone_map: ZoneMap, start: str, movement_feet: int) -> dict[str, int]:
    best, _ = _dijkstra(zone_map, start)
    return {z: cost for z, cost in sorted(best.items()) if cost <= movement_feet}


def zone_hops(zone_map: ZoneMap, a: str, b: str) -> int:
    _require(zone_map, a, b)
    depth = {a: 0}
    frontier = [a]
    while frontier:
        nxt: list[str] = []
        for here in frontier:
            for other, _ in zone_neighbors(zone_map, here):
                if other not in depth:
                    depth[other] = depth[here] + 1
                    nxt.append(other)
        frontier = nxt
    return depth[b]


def hops_for_range(feet: int) -> int:
    if feet <= MELEE_RANGE_FEET:
        return 0
    if feet <= NEAR_RANGE_FEET:
        return 1
    return MAX_RANGE_HOPS


def range_band(normal_feet: int, long_feet: int | None = None) -> RangeBand:
    normal = hops_for_range(normal_feet)
    longest = hops_for_range(max(normal_feet, long_feet)) if long_feet is not None else normal
    return RangeBand(normal_hops=normal, max_hops=longest)


def zone_range_check(zone_map: ZoneMap, a: str, b: str, band: RangeBand) -> RangeCheck:
    hops = zone_hops(zone_map, a, b)
    in_range = hops <= band.max_hops
    return RangeCheck(hops=hops, in_range=in_range, long_range=in_range and hops > band.normal_hops)


def high_ground_adv_counts(
    zone_map: ZoneMap, attacker_zone: str, target_zone: str, *, ranged: bool
) -> tuple[int, int]:
    _require(zone_map, attacker_zone, target_zone)
    attacker_high = zone_map.zone(attacker_zone).high_ground
    target_high = zone_map.zone(target_zone).high_ground
    adv = 1 if attacker_high and not target_high else 0
    dis = 1 if ranged and target_high and not attacker_high else 0
    return adv, dis


def cover_ac_bonus(zone_map: ZoneMap, attacker_zone: str, target_zone: str, *, ranged: bool) -> int:
    _require(zone_map, attacker_zone, target_zone)
    if not ranged or attacker_zone == target_zone:
        return 0
    return COVER_AC[zone_map.zone(target_zone).cover]
