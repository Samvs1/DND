"""THE surface interpreter: placing surfaces, their interactions and their triggers (SPEC 7.2).

Surfaces are data (data/bg3/surfaces.json via `aidm.data.surface_defs`); this module reads
them generically, never per surface. Every function returns events (rules never apply them);
later steps of one call see earlier ones through `rules.projection`.

- Placing (`place_surface_events`): the incoming surface meets each surface already in the zone;
  a matching pair interaction removes what it `consumes`, places what it `creates` (default
  duration, no further chain) and hits every creature in the zone with its `burst`. An incoming
  surface that is consumed is never placed (fire on water leaves only steam). A placed or
  created surface applies its "create" harms to the creatures already in the zone. The same
  kind already in the zone is replaced (fresh duration).
- Damage into a zone (`zone_damage_events`): damage of a type that matches a surface's damage
  interaction (fire into oil ignites it, cold freezes water, lightning shocks everyone in water).
- Entering (`enter_zone_events`, after the `CombatantMoved`): the mover loses the while-inside
  conditions of the zone it left, its following auras move with it, then the "enter" harms of
  every surface in the new zone apply to it.
- Turn start (`turn_start_surface_events`): the "turn_start" harms of every surface in the
  creature's zone. Durations tick per round (`rules.surface_state.surface_round_events`).

A harm with a save rolls `save_with_conditions` against the surface's DC (the caster's DC for
spell surfaces, else the data default) and is logged as `CheckResolved`; damage goes through
the damage choke point plus the concentration check (surface damage never triggers on-kill
features). Damage dice are rolled once per harm and call (an area: one roll for everyone).
`affects: hostile_to_source` spares creatures on the source's side.

Public API: `place_surface_events(rng, state, zone_id, surface) -> list[AnyEvent]`,
`zone_damage_events(rng, state, zone_id, damage_type) -> list[AnyEvent]`,
`enter_zone_events(rng, state, creature_id, from_zone) -> list[AnyEvent]`,
`turn_start_surface_events(rng, state, creature_id) -> list[AnyEvent]`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from aidm.data.surface_defs import (
    SurfaceHarm,
    SurfaceInteraction,
    SurfaceMoment,
    surface_data,
    surface_defs,
)
from aidm.models.abilities import Ability
from aidm.models.combat_events import ZoneSurfaceAdded
from aidm.models.conditions import TurnBoundary
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.dice import Roll, RollKind
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, CheckResolved, DamageTaken, DiceRolled
from aidm.models.state import GameState
from aidm.models.zones import ZoneSurface
from aidm.rules.concentration import concentration_after_damage, concentration_upkeep
from aidm.rules.condition_timing import apply_condition, new_condition
from aidm.rules.conditions import save_with_conditions
from aidm.rules.damage import resolve_damage
from aidm.rules.dice import Rng, parse_dice, roll
from aidm.rules.harm_ends import harm_ended_events
from aidm.rules.projection import project_state
from aidm.rules.surface_state import (
    inside_condition_removals,
    surface_def,
    surface_removed_events,
    surface_source,
    zone_occupants,
)


@dataclass
class _Batch:
    rng: Rng
    state: GameState
    events: list[AnyEvent] = field(default_factory=list[AnyEvent])
    rolls: dict[int, Roll] = field(default_factory=dict[int, Roll])

    def emit(self, events: Sequence[AnyEvent]) -> None:
        if events:
            self.events.extend(events)
            self.state = project_state(self.state, events)


@dataclass(frozen=True)
class _Origin:
    zone_id: str
    kind: str
    dc: int
    upcast: int = 0
    source_id: str | None = None


def _surfaces(state: GameState, zone_id: str) -> list[ZoneSurface]:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return []
    return list(enc.zone_map.zone(zone_id).surfaces) if enc.zone_map.has_zone(zone_id) else []


def _origin(zone_id: str, surface: ZoneSurface) -> _Origin:
    sdef = surface_def(surface.kind)
    dc = surface.dc if surface.dc is not None else (sdef.dc if sdef is not None else 10)
    return _Origin(zone_id, surface.kind, dc, surface.upcast, surface.source_id)


def _hurt(batch: _Batch, origin: _Origin, harm: SurfaceHarm, target_id: str, half: bool) -> None:
    if harm.damage is None or harm.damage_type is None:
        return
    dice = harm.damage
    if harm.upcast_dice and origin.upcast:
        dice = "+".join([dice, *([harm.upcast_dice] * origin.upcast)])
    rolled = batch.rolls.get(id(harm))
    if rolled is None:
        rolled = roll(str(parse_dice(dice)), batch.rng)
        batch.rolls[id(harm)] = rolled
        found = surface_defs().find(origin.kind)
        label = found.name if found is not None else origin.kind
        rolled_event = DiceRolled(
            roll=rolled, roller_id=origin.source_id, label=label, kind=RollKind.DAMAGE
        )
        batch.emit([rolled_event])
    amount = max(0, rolled.total) // 2 if half else rolled.total
    packet = DamagePacket(amount=amount, damage_type=DamageType(harm.damage_type))
    target = batch.state.creatures[target_id]
    events = resolve_damage(target, [packet], source_id=origin.source_id)
    batch.emit(events)
    if events and isinstance(events[0], DamageTaken):
        batch.emit(concentration_after_damage(batch.rng, batch.state, events[0]))
        batch.emit(harm_ended_events(batch.state, events[0]))


def _afflict(batch: _Batch, origin: _Origin, harm: SurfaceHarm, target_id: str) -> None:
    if harm.condition is None:
        return
    source = surface_source(origin.zone_id, origin.kind)
    if harm.while_inside:
        condition = new_condition(
            harm.condition, source_id=source, rounds=1, tick_on=TurnBoundary.START_OF_TURN
        )
    else:
        condition = new_condition(harm.condition, source_id=source, rounds=harm.condition_rounds)
    batch.emit(apply_condition(batch.state.creatures[target_id], condition))
    batch.emit(concentration_upkeep(batch.state, target_id))


def _apply_harm(batch: _Batch, origin: _Origin, harm: SurfaceHarm, target_id: str) -> None:
    target = batch.state.creatures.get(target_id)
    if target is None or target.dead:
        return
    half = False
    if harm.save is not None:
        dc = harm.dc if harm.dc is not None else origin.dc
        result = save_with_conditions(batch.rng, target, Ability(harm.save), dc)
        reason = f"surface {origin.kind}"
        event = CheckResolved(
            creature_id=target_id, result=result, reason=reason, source_id=origin.source_id
        )
        batch.emit([event])
        if result.success and not harm.half_on_save:
            return
        half = result.success
    _hurt(batch, origin, harm, target_id, half)
    if not half:
        _afflict(batch, origin, harm, target_id)


def _affected(state: GameState, surface: ZoneSurface, target_id: str) -> bool:
    sdef = surface_def(surface.kind)
    enc = state.encounter
    if sdef is None or sdef.affects == "all" or surface.source_id is None or enc is None:
        return True
    source = enc.combatants.get(surface.source_id)
    target = enc.combatants.get(target_id)
    return source is None or target is None or source.side != target.side


def _harm_moment(
    batch: _Batch, zone_id: str, surface: ZoneSurface, moment: SurfaceMoment, targets: Sequence[str]
) -> None:
    sdef = surface_def(surface.kind)
    if sdef is None:
        return
    origin = _origin(zone_id, surface)
    for harm in sdef.harms:
        if moment not in harm.when:
            continue
        for target_id in targets:
            if _affected(batch.state, surface, target_id):
                _apply_harm(batch, origin, harm, target_id)


def _add(batch: _Batch, zone_id: str, surface: ZoneSurface) -> None:
    batch.emit([ZoneSurfaceAdded(zone_id=zone_id, surface=surface)])
    _harm_moment(batch, zone_id, surface, "create", zone_occupants(batch.state, zone_id))


def _resolve(
    batch: _Batch, zone_id: str, existing: ZoneSurface, interaction: SurfaceInteraction
) -> None:
    if existing.kind in interaction.consumes:
        reason = "consumed by an interaction"
        batch.emit(surface_removed_events(batch.state, zone_id, existing.kind, reason))
    for kind in interaction.creates:
        sdef = surface_def(kind)
        rounds = sdef.duration_rounds if sdef is not None else None
        _add(batch, zone_id, ZoneSurface(kind=kind, rounds_left=rounds))
    if interaction.burst is not None:
        origin = _Origin(zone_id, existing.kind, interaction.burst.dc or 10)
        for target_id in zone_occupants(batch.state, zone_id):
            _apply_harm(batch, origin, interaction.burst, target_id)


def _pair(a: str, b: str) -> SurfaceInteraction | None:
    for interaction in surface_data().interactions:
        if interaction.surfaces is not None and set(interaction.surfaces) == {a, b}:
            return interaction
    return None


def _place(batch: _Batch, zone_id: str, surface: ZoneSurface) -> None:
    for existing in _surfaces(batch.state, zone_id):
        interaction = _pair(existing.kind, surface.kind)
        if interaction is None:
            continue
        _resolve(batch, zone_id, existing, interaction)
        if surface.kind in interaction.consumes:
            return
    _add(batch, zone_id, surface)


def place_surface_events(
    rng: Rng, state: GameState, zone_id: str, surface: ZoneSurface
) -> list[AnyEvent]:
    batch = _Batch(rng, state)
    _place(batch, zone_id, surface)
    return batch.events


def zone_damage_events(
    rng: Rng, state: GameState, zone_id: str, damage_type: str
) -> list[AnyEvent]:
    batch = _Batch(rng, state)
    for existing in _surfaces(state, zone_id):
        for interaction in surface_data().interactions:
            if (interaction.surface, interaction.damage_type) == (existing.kind, damage_type):
                _resolve(batch, zone_id, existing, interaction)
                break
    return batch.events


def _zone_of(state: GameState, creature_id: str) -> str | None:
    enc = state.encounter
    combatant = enc.combatants.get(creature_id) if enc is not None else None
    return combatant.zone_id if combatant is not None else None


def enter_zone_events(
    rng: Rng, state: GameState, creature_id: str, from_zone: str
) -> list[AnyEvent]:
    to_zone = _zone_of(state, creature_id)
    if to_zone is None or to_zone == from_zone:
        return []
    batch = _Batch(rng, state)
    batch.emit(inside_condition_removals(state, creature_id, from_zone))
    for surface in _surfaces(state, from_zone):
        sdef = surface_def(surface.kind)
        if sdef is not None and sdef.follows_source and surface.source_id == creature_id:
            batch.emit(surface_removed_events(batch.state, from_zone, surface.kind, "moved"))
            _place(batch, to_zone, surface)
    for surface in _surfaces(batch.state, to_zone):
        _harm_moment(batch, to_zone, surface, "enter", (creature_id,))
    return batch.events


def turn_start_surface_events(rng: Rng, state: GameState, creature_id: str) -> list[AnyEvent]:
    zone_id = _zone_of(state, creature_id)
    if zone_id is None:
        return []
    batch = _Batch(rng, state)
    for surface in _surfaces(state, zone_id):
        _harm_moment(batch, zone_id, surface, "turn_start", (creature_id,))
    return batch.events
