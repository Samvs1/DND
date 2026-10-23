"""Condition lifecycle: building, applying, removing and expiring condition instances (events only).

Public API:
- `new_condition(name, *, source_id=None, rounds=None, until_long_rest=False, tick_on=None,
  tick_creature_id=None, save_ends=None) -> ActiveCondition`: an instance with the applying
  effect's duration; when the effect gives none (`rounds` None, `until_long_rest` False) the
  data default (`ConditionDef.duration`) applies. Unknown keys raise `UnknownEntryError`.
- `apply_condition(target, condition) -> list[AnyEvent]`: `[ConditionApplied]`, or nothing for
  a dead target or one immune to the key or to a key it implies (`Creature.condition_immunities`;
  a creature immune to charmed is immune to befriended, M29.7d). An instance with the
  same (name, source) is replaced (refreshing its duration).
- `remove_condition(target, name, source_id=None) -> list[AnyEvent]`: `[ConditionRemoved]` when
  a matching instance exists (any source when `source_id` is None), else nothing.
- `turn_start_events(state, creature_id)` / `turn_end_events(rng, state, creature_id)`: at a
  turn boundary of `creature_id`, every living bearer's ROUNDS instance that ticks on this
  boundary of this creature's turn counts down (`ConditionTicked`) or expires at 0
  (`ConditionRemoved`). At the END of the bearer's own turn, each `save_ends` instance first
  rolls its save (`save_with_conditions`, logged as `CheckResolved`); a success removes it.
- `combat_end_events(state) -> list[AnyEvent]`: when combat ends, ROUNDS instances expire and
  everything else (until long rest, until removed, e.g. exhaustion or the 0-HP unconscious state)
  persists (v1 wiped every condition; SPEC 13).
- `long_rest_condition_events(creature) -> list[AnyEvent]`: a long rest ends ROUNDS and
  UNTIL_LONG_REST instances.
"""

from aidm.models.conditions import ConditionDuration, SaveEnds, TurnBoundary
from aidm.models.events import (
    AnyEvent,
    CheckResolved,
    ConditionApplied,
    ConditionRemoved,
    ConditionTicked,
)
from aidm.models.state import ActiveCondition, Creature, GameState
from aidm.rules.conditions import condition_def, save_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.monster_stats import creature_type_of


def new_condition(
    name: str,
    *,
    source_id: str | None = None,
    rounds: int | None = None,
    until_long_rest: bool = False,
    tick_on: TurnBoundary | None = None,
    tick_creature_id: str | None = None,
    save_ends: SaveEnds | None = None,
) -> ActiveCondition:
    default = condition_def(name).duration
    if rounds is not None:
        duration = ConditionDuration.ROUNDS
    elif until_long_rest:
        duration = ConditionDuration.UNTIL_LONG_REST
    else:
        duration = ConditionDuration(default.kind)
        rounds = default.rounds
    boundary = tick_on if tick_on is not None else TurnBoundary(default.tick_on)
    return ActiveCondition(
        name=name,
        source_id=source_id,
        duration=duration,
        rounds_left=rounds if duration is ConditionDuration.ROUNDS else None,
        tick_on=boundary,
        tick_creature_id=tick_creature_id,
        save_ends=save_ends,
    )


def _with_implied(name: str) -> set[str]:
    names, stack = set[str](), [name]
    while stack:
        here = stack.pop()
        if here not in names:
            names.add(here)
            stack.extend(condition_def(here).implies)
    return names


def apply_condition(target: Creature, condition: ActiveCondition) -> list[AnyEvent]:
    cdef = condition_def(condition.name)
    if target.dead or _with_implied(condition.name) & set(target.condition_immunities):
        return []
    if creature_type_of(target) in cdef.spares_types:  # M29.9a: the mindless never yield
        return []
    return [ConditionApplied(creature_id=target.id, condition=condition)]


def remove_condition(target: Creature, name: str, source_id: str | None = None) -> list[AnyEvent]:
    present = any(
        c.name == name and (source_id is None or c.source_id == source_id)
        for c in target.conditions
    )
    if not present:
        return []
    return [ConditionRemoved(creature_id=target.id, name=name, source_id=source_id)]


def _expire(bearer: Creature, c: ActiveCondition) -> ConditionRemoved:
    return ConditionRemoved(
        creature_id=bearer.id, name=c.name, source_id=c.source_id, exact_source=True
    )


def _tick(bearer: Creature, c: ActiveCondition) -> AnyEvent:
    left = (c.rounds_left or 0) - 1
    if left <= 0:
        return _expire(bearer, c)
    return ConditionTicked(
        creature_id=bearer.id, name=c.name, source_id=c.source_id, rounds_left=left
    )


type _Key = tuple[str, str, str | None]  # (bearer id, condition name, source id)


def _ticks(
    state: GameState, creature_id: str, boundary: TurnBoundary, skip: set[_Key] | None = None
) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    for bearer in state.creatures.values():
        if bearer.dead:
            continue
        for c in bearer.conditions:
            owner = c.tick_creature_id or bearer.id
            due = c.duration is ConditionDuration.ROUNDS and c.tick_on is boundary
            skipped = skip is not None and (bearer.id, c.name, c.source_id) in skip
            if due and owner == creature_id and not skipped:
                events.append(_tick(bearer, c))
    return events


def turn_start_events(state: GameState, creature_id: str) -> list[AnyEvent]:
    return _ticks(state, creature_id, TurnBoundary.START_OF_TURN)


def _save_ends(rng: Rng, bearer: Creature) -> tuple[list[AnyEvent], set[_Key]]:
    events: list[AnyEvent] = []
    ended: set[_Key] = set()
    for c in bearer.conditions:
        if c.save_ends is None:
            continue
        result = save_with_conditions(rng, bearer, c.save_ends.ability, c.save_ends.dc)
        reason = f"save ends {c.name}"
        events.append(CheckResolved(creature_id=bearer.id, result=result, reason=reason))
        if result.success:
            events.append(_expire(bearer, c))
            ended.add((bearer.id, c.name, c.source_id))
    return events, ended


def turn_end_events(rng: Rng, state: GameState, creature_id: str) -> list[AnyEvent]:
    bearer = state.creatures.get(creature_id)
    events: list[AnyEvent] = []
    ended: set[_Key] = set()
    if bearer is not None and not bearer.dead:
        events, ended = _save_ends(rng, bearer)
    return events + _ticks(state, creature_id, TurnBoundary.END_OF_TURN, ended)


def combat_end_events(state: GameState) -> list[AnyEvent]:
    return [
        _expire(bearer, c)
        for bearer in state.creatures.values()
        for c in bearer.conditions
        if not c.persists_after_combat
    ]


def long_rest_condition_events(creature: Creature) -> list[AnyEvent]:
    ends = (ConditionDuration.ROUNDS, ConditionDuration.UNTIL_LONG_REST)
    return [_expire(creature, c) for c in creature.conditions if c.duration in ends]
