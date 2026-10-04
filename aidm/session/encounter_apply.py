"""Reducer part for the encounter events (called only by `aidm.session.reducer.apply`).

Same semantics as the reducer: plain assignment of resolved values, payloads copied on insert,
`ReducerError` for an event that does not fit the state (an engine bug). `event_count` is
incremented by the caller.

Public API: `EncounterEvent` (the union of the encounter events),
`apply_encounter_event(state, event) -> None`.
"""

from typing import assert_never

from aidm.models.encounter import Combatant, Encounter, EncounterStatus
from aidm.models.encounter_events import (
    CombatantWithdrew,
    EconomyChanged,
    EncounterEnded,
    EncounterStarted,
    TurnEnded,
    TurnStarted,
)
from aidm.models.state import GameState
from aidm.session.reducer_errors import ReducerError

type EncounterEvent = (
    EncounterStarted | TurnStarted | TurnEnded | EconomyChanged | CombatantWithdrew | EncounterEnded
)


def _active(state: GameState) -> Encounter:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        raise ReducerError("no active encounter")
    return enc


def _combatant(enc: Encounter, creature_id: str) -> Combatant:
    try:
        return enc.combatants[creature_id]
    except KeyError:
        raise ReducerError(f"{creature_id!r} is not in the encounter") from None


def _start(state: GameState, event: EncounterStarted) -> None:
    if state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE:
        raise ReducerError("an encounter is already active")
    missing = [cid for cid in event.encounter.combatants if cid not in state.creatures]
    if missing:
        raise ReducerError(f"encounter names unknown creatures {missing}")
    state.encounter = event.encounter.model_copy(deep=True)


def _turn_started(enc: Encounter, event: TurnStarted) -> None:
    if event.active_index >= len(enc.initiative):
        raise ReducerError(f"initiative index {event.active_index} out of range")
    if enc.initiative[event.active_index].creature_id != event.creature_id:
        raise ReducerError(f"{event.creature_id!r} is not at initiative index {event.active_index}")
    _combatant(enc, event.creature_id).economy = event.economy
    enc.round = event.round
    enc.active_index = event.active_index
    enc.turn_open = True


def apply_encounter_event(state: GameState, event: EncounterEvent) -> None:
    if isinstance(event, EncounterStarted):
        _start(state, event)
        return
    enc = _active(state)
    match event:
        case TurnStarted():
            _turn_started(enc, event)
        case TurnEnded(creature_id=cid):
            if enc.active_id() != cid:
                raise ReducerError(f"{cid!r} has no open turn to end")
            enc.turn_open = False
        case EconomyChanged(creature_id=cid, economy=economy):
            _combatant(enc, cid).economy = economy
        case CombatantWithdrew(creature_id=cid, reason=reason):
            _combatant(enc, cid).withdrawn = reason
        case EncounterEnded(status=status):
            enc.status = status
            enc.turn_open = False
        case _:
            assert_never(event)
