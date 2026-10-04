"""The reducer: the ONLY code that mutates `GameState` (SPEC 2.5, 5).

Public API:
- `apply(state, event) -> GameState`: applies one event IN PLACE and returns the same `state`
  object (for chaining). In-place mutation is deliberate: the table actor owns its state
  exclusively, and combat sims apply many thousands of events, so copying per event is too slow.
  Callers that need the old value must `state.model_copy(deep=True)` first.
- `replay(initial, events) -> GameState`: deep-copies `initial` and applies every event in order.
  `initial` is never modified. `replay(s0, log)` must equal the live state (tested).
- `ReducerError(ValueError)`: the event does not fit the state (unknown creature id, duplicate
  id). This is always an engine bug: rules must only emit events valid for the current state.

Semantics: every event increments `state.event_count` (log-only events included) and then does
plain assignment of the resolved values it carries. The reducer never rolls dice, reads data or
re-derives rules, so replay is exact. Payload objects are copied on insert, so later mutation of
state never changes a logged event. Exhaustiveness: a new `AnyEvent` member without a `case` here
fails pyright via `assert_never`.
"""

from collections.abc import Iterable
from typing import assert_never

from aidm.models.events import (
    AnyEvent,
    CampSuppliesChanged,
    CheckResolved,
    ConcentrationEnded,
    ConcentrationStarted,
    ConditionApplied,
    ConditionRemoved,
    ConditionTicked,
    CreatureAdded,
    CreatureDied,
    CreatureRemoved,
    DamageTaken,
    DeathSaveRolled,
    DeathSavesSet,
    DiceRolled,
    HpChanged,
    LongRestTaken,
    ResourceSet,
    ShortRestTaken,
    Stabilized,
    TempHpSet,
)
from aidm.models.state import ActiveCondition, Creature, GameState


class ReducerError(ValueError):
    """An event that cannot apply to the current state (an engine bug)."""


def _creature(state: GameState, creature_id: str) -> Creature:
    try:
        return state.creatures[creature_id]
    except KeyError:
        raise ReducerError(f"unknown creature id {creature_id!r}") from None


def _add_creature(state: GameState, creature: Creature) -> None:
    if creature.id in state.creatures:
        raise ReducerError(f"duplicate creature id {creature.id!r}")
    state.creatures[creature.id] = creature.model_copy(deep=True)


def _apply_condition(creature: Creature, condition: ActiveCondition) -> None:
    kept = [
        c
        for c in creature.conditions
        if (c.name, c.source_id) != (condition.name, condition.source_id)
    ]
    kept.append(condition)
    creature.conditions = kept


def _remove_condition(creature: Creature, event: ConditionRemoved) -> None:
    name, source_id = event.name, event.source_id
    if event.exact_source:
        creature.conditions = [
            c for c in creature.conditions if (c.name, c.source_id) != (name, source_id)
        ]
        return
    creature.conditions = [
        c
        for c in creature.conditions
        if c.name != name or (source_id is not None and c.source_id != source_id)
    ]


def _tick_condition(creature: Creature, event: ConditionTicked) -> None:
    key = (event.name, event.source_id)
    for i, c in enumerate(creature.conditions):
        if (c.name, c.source_id) == key and c.rounds_left is not None:
            creature.conditions[i] = c.model_copy(update={"rounds_left": event.rounds_left})
            return
    raise ReducerError(f"{creature.id!r} has no ROUNDS condition {key!r} to tick")


def apply(state: GameState, event: AnyEvent) -> GameState:
    match event:
        case CreatureAdded(creature=creature):
            _add_creature(state, creature)
        case CreatureRemoved(creature_id=cid):
            _creature(state, cid)
            del state.creatures[cid]
        case HpChanged(creature_id=cid, new_hp=new_hp):
            _creature(state, cid).hp = new_hp
        case TempHpSet(creature_id=cid, temp_hp=temp_hp):
            _creature(state, cid).temp_hp = temp_hp
        case ConditionApplied(creature_id=cid, condition=condition):
            _apply_condition(_creature(state, cid), condition)
        case ConditionRemoved(creature_id=cid):
            _remove_condition(_creature(state, cid), event)
        case ConditionTicked(creature_id=cid):
            _tick_condition(_creature(state, cid), event)
        case ConcentrationStarted(creature_id=cid, concentration=concentration):
            _creature(state, cid).concentrating_on = concentration
        case ConcentrationEnded(creature_id=cid):
            _creature(state, cid).concentrating_on = None
        case DeathSaveRolled(creature_id=cid, successes=successes, failures=failures):
            target = _creature(state, cid)
            target.death_save_successes = successes
            target.death_save_failures = failures
        case DeathSavesSet(creature_id=cid, successes=successes, failures=failures, stable=stable):
            target = _creature(state, cid)
            target.death_save_successes = successes
            target.death_save_failures = failures
            target.stable = stable
        case Stabilized(creature_id=cid):
            target = _creature(state, cid)
            target.stable = True
            target.death_save_successes = 0
            target.death_save_failures = 0
        case CreatureDied(creature_id=cid):
            target = _creature(state, cid)
            target.dead = True
            target.stable = False
        case ResourceSet(creature_id=cid, key=key, resource=resource):
            _creature(state, cid).resources[key] = resource
        case CampSuppliesChanged(camp_supplies=supplies):
            state.camp_supplies = supplies
        case ShortRestTaken(short_rests_used=used):
            state.short_rests_used = used
        case LongRestTaken(camp_supplies=supplies):
            state.camp_supplies = supplies
            state.short_rests_used = 0
        case DiceRolled() | CheckResolved() | DamageTaken():
            pass
        case _:
            assert_never(event)
    state.event_count += 1
    return state


def replay(initial: GameState, events: Iterable[AnyEvent]) -> GameState:
    state = initial.model_copy(deep=True)
    for event in events:
        apply(state, event)
    return state
