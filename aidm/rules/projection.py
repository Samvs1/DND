"""Read-only projection: what the state WILL look like after a batch of not-yet-applied events.

Rules resolve multi-step commands (an attack that drops a concentrating target, a spell that
hits three creatures) as one event list. Later steps must see the effect of earlier ones, but
rules never apply events (only `aidm.session.reducer.apply` does). `project_state` answers the
question on private copies: the input state and its objects are never touched.

Covered events (the ones rules emit mid-command; everything else is ignored): HpChanged,
TempHpSet, ConditionApplied, ConditionRemoved, ConditionTicked, ConcentrationStarted,
ConcentrationEnded, DeathSaveRolled, DeathSavesSet, Stabilized, CreatureDied, ResourceSet,
EconomyChanged and CombatantMoved. The semantics mirror the reducer exactly (property-tested
against it in tests/property/test_projection_props.py).

Public API:
- `project_creature(creature, events) -> Creature`: the creature after the events naming it.
- `project_state(state, events) -> GameState`: a shallow state copy whose touched creatures and
  encounter are projected copies (untouched creatures are shared, read-only).
"""

from collections.abc import Sequence

from aidm.models.combat_events import CombatantMoved
from aidm.models.encounter_events import EconomyChanged
from aidm.models.events import (
    AnyEvent,
    ConcentrationEnded,
    ConcentrationStarted,
    ConditionApplied,
    ConditionRemoved,
    ConditionTicked,
    CreatureDied,
    DeathSaveRolled,
    DeathSavesSet,
    HpChanged,
    ResourceSet,
    Stabilized,
    TempHpSet,
)
from aidm.models.state import ActiveCondition, Creature, GameState


def _without(conditions: list[ActiveCondition], event: ConditionRemoved) -> list[ActiveCondition]:
    name, src = event.name, event.source_id
    if event.exact_source:
        return [c for c in conditions if (c.name, c.source_id) != (name, src)]
    return [c for c in conditions if c.name != name or (src is not None and c.source_id != src)]


def _with(conditions: list[ActiveCondition], new: ActiveCondition) -> list[ActiveCondition]:
    kept = [c for c in conditions if (c.name, c.source_id) != (new.name, new.source_id)]
    return [*kept, new]


def _ticked(conditions: list[ActiveCondition], event: ConditionTicked) -> list[ActiveCondition]:
    key = (event.name, event.source_id)
    return [
        c.model_copy(update={"rounds_left": event.rounds_left})
        if (c.name, c.source_id) == key and c.rounds_left is not None
        else c
        for c in conditions
    ]


def _step(c: Creature, event: AnyEvent) -> None:
    match event:
        case HpChanged(new_hp=hp):
            c.hp = hp
        case TempHpSet(temp_hp=temp):
            c.temp_hp = temp
        case ConditionApplied(condition=new):
            c.conditions = _with(c.conditions, new)
        case ConditionRemoved():
            c.conditions = _without(c.conditions, event)
        case ConditionTicked():
            c.conditions = _ticked(c.conditions, event)
        case ConcentrationStarted(concentration=conc):
            c.concentrating_on = conc
        case ConcentrationEnded():
            c.concentrating_on = None
        case DeathSaveRolled(successes=s, failures=f):
            c.death_save_successes, c.death_save_failures = s, f
        case DeathSavesSet(successes=s, failures=f, stable=stable):
            c.death_save_successes, c.death_save_failures, c.stable = s, f, stable
        case Stabilized():
            c.stable, c.death_save_successes, c.death_save_failures = True, 0, 0
        case CreatureDied():
            c.dead, c.stable = True, False
        case ResourceSet(key=key, resource=resource):
            c.resources = {**c.resources, key: resource}
        case _:
            pass


def _target(event: AnyEvent) -> str | None:
    return getattr(event, "creature_id", None)


def project_creature(creature: Creature, events: Sequence[AnyEvent]) -> Creature:
    projected = creature.model_copy(deep=True)
    for event in events:
        if _target(event) == creature.id:
            _step(projected, event)
    return projected


def project_state(state: GameState, events: Sequence[AnyEvent]) -> GameState:
    touched = {cid for e in events if (cid := _target(e)) in state.creatures}
    creatures = dict(state.creatures)
    for cid in sorted(touched):
        creatures[cid] = project_creature(state.creatures[cid], events)
    encounter = state.encounter
    moves = [e for e in events if isinstance(e, (EconomyChanged, CombatantMoved))]
    if encounter is not None and moves:
        encounter = encounter.model_copy(deep=True)
        for event in moves:
            combatant = encounter.combatants.get(event.creature_id)
            if combatant is None:
                continue
            if isinstance(event, EconomyChanged):
                combatant.economy = event.economy
            else:
                combatant.zone_id = event.to_zone
    return state.model_copy(update={"creatures": creatures, "encounter": encounter})
