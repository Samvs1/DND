"""Seeded zone-map generation from terrain tags (SPEC 7.3).

`generate_zone_map(rng, tags, terrains) -> ZoneMap`:
1. The known terrain tags, in the order given (duplicates and unknown tags dropped; case and
   surrounding blanks ignored). None known: the fallback terrain ("wilds").
2. The candidate zones are the templates of every known terrain, in order (first key wins).
   Edges cost the FIRST known terrain's `hop_feet`.
3. 3 to 6 zones (never more than the candidates) are drawn with a seeded shuffle; each gets one
   of its template names.
4. A random spanning tree (zone i links to one of zones 0..i-1) guarantees a connected graph;
   every other pair is then linked with probability 1/4 for loops.
Same rng seed + same tags + same templates -> the same map (only `rng.randint` is used).
The terrain registry is an argument (`aidm.data.zone_templates.zone_templates()` by default in
the callers); rules never load data.
"""

from collections.abc import Sequence

from aidm.data.registry import Registry
from aidm.data.zone_templates import FALLBACK_TERRAIN, TerrainTemplate, ZoneTemplate
from aidm.models.zones import CoverLevel, Zone, ZoneEdge, ZoneMap
from aidm.rules.dice import Rng

MIN_GENERATED_ZONES = 3
MAX_GENERATED_ZONES = 6
EXTRA_EDGE_ODDS = 4  # each non-tree pair is linked when randint(1, 4) == 1


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


def _zone(rng: Rng, template: ZoneTemplate) -> Zone:
    return Zone(
        id=template.key,
        name=template.names[rng.randint(0, len(template.names) - 1)],
        tags=list(template.tags),
        distance_label=template.distance_label,
        cover=CoverLevel(template.cover),
        high_ground=template.high_ground,
        difficult=template.difficult,
    )


def _edges(rng: Rng, ids: list[str], feet: int) -> list[ZoneEdge]:
    linked: set[frozenset[str]] = set()
    edges: list[ZoneEdge] = []
    for i in range(1, len(ids)):
        j = rng.randint(0, i - 1)
        linked.add(frozenset((ids[j], ids[i])))
        edges.append(ZoneEdge(a=ids[j], b=ids[i], feet=feet))
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            pair = frozenset((ids[i], ids[j]))
            if pair not in linked and rng.randint(1, EXTRA_EDGE_ODDS) == 1:
                edges.append(ZoneEdge(a=ids[i], b=ids[j], feet=feet))
    return edges


def generate_zone_map(
    rng: Rng, tags: Sequence[str], terrains: Registry[TerrainTemplate]
) -> ZoneMap:
    chosen = _terrains(tags, terrains)
    pool = _pool(chosen)
    top = min(MAX_GENERATED_ZONES, len(pool))
    count = rng.randint(min(MIN_GENERATED_ZONES, top), top)
    picked = _shuffled(rng, pool)[:count]
    zones = [_zone(rng, t) for t in picked]
    edges = _edges(rng, [z.id for z in zones], chosen[0].hop_feet)
    return ZoneMap(zones=zones, edges=edges)
