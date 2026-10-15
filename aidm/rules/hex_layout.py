"""Hex positions of a fight's zones (M21: the screen draws the battle map as touching hexes).

Axial coordinates (q, r), pointy-top: the six neighbours of a hex are `HEX_DIRECTIONS` away.
Generated maps (`aidm.rules.zone_gen`) store a hex on every zone and link exactly the touching
pairs, so the picture IS the movement graph. `hex_layout(zone_map)` returns those stored
positions; a map from before M21 (no hexes) gets a deterministic best fit: zones in breadth-
first order from the first, each on the free hex beside an already placed linked zone that
touches the most linked and the fewest unlinked placed zones (direction order breaks ties). A fit
cannot always be exact (four mutually linked zones do not fit on hexes); the screen then still
shows every zone, and its move list stays the authority.

Public API: `HEX_DIRECTIONS`, `Hex` (a (q, r) pair), `hex_neighbours(cell)`, `touching(a, b)`,
`hex_layout(zone_map) -> dict[str, Hex]`.
"""

from aidm.models.zones import ZoneMap

type Hex = tuple[int, int]

HEX_DIRECTIONS: tuple[Hex, ...] = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))


def hex_neighbours(cell: Hex) -> list[Hex]:
    q, r = cell
    return [(q + dq, r + dr) for dq, dr in HEX_DIRECTIONS]


def touching(a: Hex, b: Hex) -> bool:
    return (b[0] - a[0], b[1] - a[1]) in HEX_DIRECTIONS


def _links(zone_map: ZoneMap) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {z.id: [] for z in zone_map.zones}
    for edge in zone_map.edges:
        out[edge.a].append(edge.b)
        out[edge.b].append(edge.a)
    return out


def _bfs_order(zone_map: ZoneMap, links: dict[str, list[str]]) -> list[str]:
    order = [zone_map.zones[0].id]
    for here in order:
        order += [z for z in links[here] if z not in order]
    return order + [z.id for z in zone_map.zones if z.id not in order]


def _score(cell: Hex, zone_id: str, placed: dict[str, Hex], links: dict[str, list[str]]) -> int:
    near = [other for other, at in placed.items() if touching(cell, at)]
    linked = sum(1 for other in near if other in links[zone_id])
    return linked * 10 - (len(near) - linked)


def _best_fit(zone_map: ZoneMap) -> dict[str, Hex]:
    links = _links(zone_map)
    placed: dict[str, Hex] = {}
    for zone_id in _bfs_order(zone_map, links):
        if not placed:
            placed[zone_id] = (0, 0)
            continue
        anchors = [placed[z] for z in links[zone_id] if z in placed] or list(placed.values())
        taken = set(placed.values())
        free = [c for a in anchors for c in hex_neighbours(a) if c not in taken]
        placed[zone_id] = max(free, key=lambda c: _score(c, zone_id, placed, links))
    return placed


def hex_layout(zone_map: ZoneMap) -> dict[str, Hex]:
    stored = {z.id: (z.hex.q, z.hex.r) for z in zone_map.zones if z.hex is not None}
    if len(stored) == len(zone_map.zones):
        return stored
    return _best_fit(zone_map)
