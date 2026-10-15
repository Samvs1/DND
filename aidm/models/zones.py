"""Zones: the abstract battlefield of an encounter (SPEC 7.3; no pixel grid).

An encounter happens on a small undirected graph of 1 to 6 zones (generated maps have 3 to 6).
Creatures stand IN a zone (`aidm.models.encounter.Combatant.zone_id`); there is no position
inside a zone. Everything mechanical about distance is derived from the graph by
`aidm.rules.zones`: movement spends feet per hop, melee needs the same zone, ranged attacks and
spells reach a number of hops given by their range band.

Public API:
- `CoverLevel`: NONE / HALF (+2 AC) / THREE_QUARTERS (+5 AC) for ranged attacks INTO the zone
  from another zone (numbers live in `aidm.rules.zones`).
- `ZoneSurface(kind, rounds_left, source_id, dc, upcast, concentration)`: one surface lying in a
  zone (`kind` keys data/bg3/surfaces.json; at most one per kind per zone). `rounds_left` None =
  until removed; `source_id` the creature that made it (None for the environment); `dc` the save
  DC it imposes (None = the data default); `upcast` slot levels above the creating spell's level;
  `concentration` True when it ends with its source's concentration.
- `HexCoord(q, r)`: an axial hex position on the battle map (M21: generated maps place every
  zone on a hex, and two zones are linked exactly when their hexes touch).
- `Zone(id, name, tags, distance_label, cover, high_ground, difficult, surfaces, hex)`: `id` is the
  stable key tools and the UI use ("ridge"); `name` is the display name ("Mossy Ridge");
  `distance_label` is flavour for the zone card ("about 30 ft across"); `difficult` doubles the
  feet it costs to ENTER the zone; `hex` is its map position (None in saves from before M21:
  `aidm.rules.hex_layout` then fits one).
- `ZoneEdge(a, b, feet)`: an undirected adjacency; `feet` is the movement cost of one hop.
- `ZoneMap(zones, edges)`: validated on construction: 1-6 zones, unique ids, edges between known
  distinct zones, no duplicate edge, the graph is connected (every zone is reachable), and no two
  zones share a hex.
  `zone(zone_id)` / `has_zone(zone_id)` are lookups only.
- Rule results (frozen): `ZonePath(zones, feet)`, `RangeBand(normal_hops, max_hops)`,
  `RangeCheck(hops, in_range, long_range)`.

`Zone` and `ZoneMap` are state models: mutable, `extra="forbid"`, new fields need defaults.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_ZONES = 6


class CoverLevel(StrEnum):
    NONE = "none"
    HALF = "half"
    THREE_QUARTERS = "three_quarters"


class ZoneSurface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    rounds_left: int | None = Field(default=None, ge=1)
    source_id: str | None = None
    dc: int | None = Field(default=None, ge=1)
    upcast: int = Field(default=0, ge=0)
    concentration: bool = False


class HexCoord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    q: int
    r: int


class Zone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list[str])
    distance_label: str = ""
    cover: CoverLevel = CoverLevel.NONE
    high_ground: bool = False
    difficult: bool = False
    surfaces: list[ZoneSurface] = Field(default_factory=list[ZoneSurface])
    hex: HexCoord | None = None


class ZoneEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: str = Field(min_length=1)
    b: str = Field(min_length=1)
    feet: int = Field(default=30, ge=5)

    @model_validator(mode="after")
    def _check_ends(self) -> "ZoneEdge":
        if self.a == self.b:
            raise ValueError(f"edge {self.a!r} connects a zone to itself")
        return self

    def key(self) -> frozenset[str]:
        return frozenset((self.a, self.b))


class ZoneMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zones: list[Zone] = Field(min_length=1, max_length=MAX_ZONES)
    edges: list[ZoneEdge] = Field(default_factory=list[ZoneEdge])

    @model_validator(mode="after")
    def _check_graph(self) -> "ZoneMap":
        ids = [z.id for z in self.zones]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate zone ids in {ids}")
        seen: set[frozenset[str]] = set()
        for edge in self.edges:
            if edge.a not in ids or edge.b not in ids:
                raise ValueError(f"edge {edge.a!r}-{edge.b!r} names an unknown zone")
            if edge.key() in seen:
                raise ValueError(f"duplicate edge {edge.a!r}-{edge.b!r}")
            seen.add(edge.key())
        reached = {ids[0]}
        frontier = [ids[0]]
        while frontier:
            here = frontier.pop()
            for edge in self.edges:
                if here in (edge.a, edge.b):
                    other = edge.b if here == edge.a else edge.a
                    if other not in reached:
                        reached.add(other)
                        frontier.append(other)
        if len(reached) != len(ids):
            raise ValueError(f"zone graph is not connected: {sorted(set(ids) - reached)}")
        placed = [z.hex for z in self.zones if z.hex is not None]
        if len(set(placed)) != len(placed):
            raise ValueError("two zones share a hex")
        return self

    def has_zone(self, zone_id: str) -> bool:
        return any(z.id == zone_id for z in self.zones)

    def zone(self, zone_id: str) -> Zone:
        for z in self.zones:
            if z.id == zone_id:
                return z
        raise KeyError(zone_id)


class ZonePath(BaseModel):
    """A cheapest route: `zones` from start to goal inclusive, `feet` the movement it costs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    zones: tuple[str, ...] = Field(min_length=1)
    feet: int = Field(ge=0)


class RangeBand(BaseModel):
    """How many hops an attack or spell reaches: up to `normal_hops` without penalty, up to
    `max_hops` at disadvantage (long range). Melee and touch are (0, 0)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    normal_hops: int = Field(ge=0)
    max_hops: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_order(self) -> "RangeBand":
        if self.max_hops < self.normal_hops:
            raise ValueError("max_hops must be >= normal_hops")
        return self


class RangeCheck(BaseModel):
    """The result of checking a band between two zones: `hops` apart, `in_range`, and
    `long_range` (in range only at disadvantage)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hops: int = Field(ge=0)
    in_range: bool
    long_range: bool = False
