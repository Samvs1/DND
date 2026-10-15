"""Seeded zone-map generation from terrain tags (SPEC 7.3).

`generate_zone_map(rng, tags, terrains) -> ZoneMap`:
1. The known terrain tags, in the order given (duplicates and unknown tags dropped; case and
   surrounding blanks ignored). None known: the fallback terrain ("wilds").
2. The candidate zones are the templates of every known terrain, in order (first key wins).
   Edges cost the FIRST known terrain's `hop_feet`.
3. 3 to 6 zones (never more than the candidates) are drawn with a seeded shuffle; each gets one
   of its template names.
4. M21 (owner: "hexagonal grids that fit into each other so it's clear which zone is next to
   which one"): the zones are placed on hexes as a seeded connected cluster (`_cluster`): the
   first at (0, 0), each next one on a free hex beside the cluster, drawn with weight = the number
   of placed hexes it touches (compact shapes), within `MAX_HEX_ROWS` rows so it fits the screen.
   EVERY pair of touching hexes is linked and nothing else, so the map on the screen is exactly
   the movement graph (`aidm.rules.hex_layout`).
Same rng seed + same tags + same templates -> the same map (only `rng.randint` is used).
The terrain registry is an argument (`aidm.data.zone_templates.zone_templates()` by default in
the callers); rules never load data.
"""

from collections.abc import Sequence

from aidm.data.registry import Registry
from aidm.data.zone_templates import FALLBACK_TERRAIN, TerrainTemplate, ZoneTemplate
from aidm.models.zones import CoverLevel, HexCoord, Zone, ZoneEdge, ZoneMap
from aidm.rules.dice import Rng
from aidm.rules.hex_layout import Hex, hex_neighbours, touching

MIN_GENERATED_ZONES = 3
MAX_GENERATED_ZONES = 6
MAX_HEX_ROWS = 2  # the screen shows hexes big enough to read on a TV (M21.2)


def _terrains(tags: Sequence[str], terrains: Registry[TerrainTemplate]) -> list[TerrainTemplate]:
    wanted = dict.fromkeys(t.strip().lower() for t in tags)
    known = [terrains.get(t) for t in wanted if t in terrains]
    return known or [terrains.get(FALLBACK_TERRAIN)]


def _pool(chosen: list[TerrainTemplate]) -> list[ZoneTemplate]:
    by_key: dict[str, ZoneTemplate] = {}
    for terrain in chosen:
        for template in terrain.zones:
            by_key.setdefault(template.key, template)
    return list(by_key.values())


def _shuffled[T](rng: Rng, items: list[T]) -> list[T]:
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        j = rng.randint(0, i)
        out[i], out[j] = out[j], out[i]
    return out


def _zone(rng: Rng, template: ZoneTemplate, cell: Hex) -> Zone:
    return Zone(
        id=template.key,
        name=template.names[rng.randint(0, len(template.names) - 1)],
        tags=list(template.tags),
        distance_label=template.distance_label,
        cover=CoverLevel(template.cover),
        high_ground=template.high_ground,
        difficult=template.difficult,
        hex=HexCoord(q=cell[0], r=cell[1]),
    )


def _frontier(cells: list[Hex]) -> list[Hex]:
    """Free hexes beside the cluster that keep it within MAX_HEX_ROWS rows, each listed once per
    placed hex it touches (the weight), in a fixed order."""
    rows = [r for _, r in cells]
    out: list[Hex] = []
    for cell in cells:
        for near in hex_neighbours(cell):
            span = max(*rows, near[1]) - min(*rows, near[1]) + 1
            if near not in cells and span <= MAX_HEX_ROWS:
                out.append(near)
    return sorted(out)


def _cluster(rng: Rng, count: int) -> list[Hex]:
    cells: list[Hex] = [(0, 0)]
    while len(cells) < count:
        options = _frontier(cells)
        cells.append(options[rng.randint(0, len(options) - 1)])
    return cells


def _edges(ids: list[str], cells: list[Hex], feet: int) -> list[ZoneEdge]:
    edges: list[ZoneEdge] = []
    for i, a in enumerate(ids):
        for j in range(i + 1, len(ids)):
            if touching(cells[i], cells[j]):
                edges.append(ZoneEdge(a=a, b=ids[j], feet=feet))
    return edges


def generate_zone_map(
    rng: Rng, tags: Sequence[str], terrains: Registry[TerrainTemplate]
) -> ZoneMap:
    chosen = _terrains(tags, terrains)
    pool = _pool(chosen)
    top = min(MAX_GENERATED_ZONES, len(pool))
    count = rng.randint(min(MIN_GENERATED_ZONES, top), top)
    picked = _shuffled(rng, pool)[:count]
    cells = _cluster(rng, len(picked))
    zones = [_zone(rng, t, cell) for t, cell in zip(picked, cells, strict=True)]
    edges = _edges([z.id for z in zones], cells, chosen[0].hop_feet)
    return ZoneMap(zones=zones, edges=edges)
