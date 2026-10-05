"""Surface bookkeeping that needs no dice: lookups, removal, round ticks (SPEC 7.2 surfaces).

The interpreter with dice and damage is `aidm.rules.surfaces`; this module stays below it so
`rules.concentration` can end concentration surfaces without an import cycle.

A condition a surface applies carries the source id `surface:<zone id>:<kind>`
(`surface_source`), so it can be found again when its bearer leaves the zone or the surface
goes away. Only `while_inside` conditions (data/bg3/surfaces.json) end that way.

Public API:
- `surface_def(kind) -> SurfaceDef | None` (None for a kind without data: inert).
- `surface_source(zone_id, kind) -> str`; `zone_surface(state, zone_id, kind) -> ZoneSurface |
  None`; `zone_occupants(state, zone_id) -> tuple[str, ...]` (living combatants still in the
  fight, in combatant order).
- `inside_condition_removals(state, creature_id, zone_id, kind=None) -> list[AnyEvent]`: the
  `ConditionRemoved` events for the creature's while-inside conditions from that zone's surfaces
  (one kind, or all of them).
- `surface_removed_events(state, zone_id, kind, reason) -> list[AnyEvent]`: `ZoneSurfaceRemoved`
  plus the while-inside condition removals of every creature in the zone.
- `surface_round_events(state) -> list[AnyEvent]`: a new round started: every surface with a
  duration counts down (`ZoneSurfaceTicked`) or goes away at 0.
- `concentration_surface_events(state, caster_id) -> list[AnyEvent]`: removes every surface the
  caster keeps up with concentration (called when that concentration ends).
"""

from aidm.data.surface_defs import SurfaceDef, surface_defs
from aidm.models.combat_events import ZoneSurfaceRemoved, ZoneSurfaceTicked
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.events import AnyEvent, ConditionRemoved
from aidm.models.state import GameState
from aidm.models.zones import ZoneSurface

SURFACE_SOURCE_PREFIX = "surface:"


def surface_def(kind: str) -> SurfaceDef | None:
    return surface_defs().find(kind)


def surface_source(zone_id: str, kind: str) -> str:
    return f"{SURFACE_SOURCE_PREFIX}{zone_id}:{kind}"


def _active(state: GameState) -> Encounter | None:
    enc = state.encounter
    return enc if enc is not None and enc.status is EncounterStatus.ACTIVE else None


def zone_surface(state: GameState, zone_id: str, kind: str) -> ZoneSurface | None:
    enc = _active(state)
    if enc is None or not enc.zone_map.has_zone(zone_id):
        return None
    return next((s for s in enc.zone_map.zone(zone_id).surfaces if s.kind == kind), None)


def zone_occupants(state: GameState, zone_id: str) -> tuple[str, ...]:
    enc = _active(state)
    if enc is None:
        return ()
    found: list[str] = []
    for cid, combatant in enc.combatants.items():
        creature = state.creatures.get(cid)
        if creature is None or creature.dead or combatant.withdrawn is not None:
            continue
        if combatant.zone_id == zone_id:
            found.append(cid)
    return tuple(found)


def _inside_names(kind: str) -> set[str]:
    sdef = surface_def(kind)
    if sdef is None:
        return set()
    return {h.condition for h in sdef.harms if h.while_inside and h.condition is not None}


def inside_condition_removals(
    state: GameState, creature_id: str, zone_id: str, kind: str | None = None
) -> list[AnyEvent]:
    creature = state.creatures.get(creature_id)
    if creature is None:
        return []
    events: list[AnyEvent] = []
    prefix = f"{SURFACE_SOURCE_PREFIX}{zone_id}:"
    for c in creature.conditions:
        src = c.source_id or ""
        if not src.startswith(prefix):
            continue
        src_kind = src[len(prefix) :]
        if (kind is None or src_kind == kind) and c.name in _inside_names(src_kind):
            events.append(
                ConditionRemoved(
                    creature_id=creature_id, name=c.name, source_id=src, exact_source=True
                )
            )
    return events


def surface_removed_events(
    state: GameState, zone_id: str, kind: str, reason: str
) -> list[AnyEvent]:
    events: list[AnyEvent] = [ZoneSurfaceRemoved(zone_id=zone_id, kind=kind, reason=reason)]
    for cid in zone_occupants(state, zone_id):
        events.extend(inside_condition_removals(state, cid, zone_id, kind))
    return events


def surface_round_events(state: GameState) -> list[AnyEvent]:
    enc = _active(state)
    if enc is None:
        return []
    events: list[AnyEvent] = []
    for zone in enc.zone_map.zones:
        for surface in zone.surfaces:
            if surface.rounds_left is None:
                continue
            left = surface.rounds_left - 1
            if left <= 0:
                events.extend(surface_removed_events(state, zone.id, surface.kind, "expired"))
            else:
                events.append(
                    ZoneSurfaceTicked(zone_id=zone.id, kind=surface.kind, rounds_left=left)
                )
    return events


def concentration_surface_events(state: GameState, caster_id: str) -> list[AnyEvent]:
    enc = _active(state)
    if enc is None:
        return []
    events: list[AnyEvent] = []
    for zone in enc.zone_map.zones:
        for surface in zone.surfaces:
            if surface.concentration and surface.source_id == caster_id:
                events.extend(
                    surface_removed_events(state, zone.id, surface.kind, "concentration ended")
                )
    return events
