"""Reducer: encounter events assign resolved values and reject events that do not fit."""

from __future__ import annotations

import pytest

from aidm.models.encounter import (
    Combatant,
    Encounter,
    EncounterStatus,
    InitiativeEntry,
    Side,
    TurnEconomy,
    WithdrawReason,
)
from aidm.models.encounter_events import (
    CombatantWithdrew,
    EconomyChanged,
    EncounterEnded,
    EncounterStarted,
    TurnEnded,
    TurnStarted,
)
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.session.reducer import ReducerError, apply
from tests.unit.rules.encounter_fixtures import small_map


def _state() -> GameState:
    state = GameState(campaign_id="r", seed=0)
    for cid in ("a", "b"):
        state.creatures[cid] = Creature(id=cid, name=cid, kind=CreatureKind.PC, max_hp=10, hp=10)
    return state


def _encounter() -> Encounter:
    return Encounter(
        id="e",
        zone_map=small_map(),
        combatants={
            "a": Combatant(creature_id="a", side=Side.PARTY, zone_id="gate"),
            "b": Combatant(creature_id="b", side=Side.HOSTILE, zone_id="yard"),
        },
        initiative=[
            InitiativeEntry(creature_id="b", roll=4, modifier=1, total=5, dex=12),
            InitiativeEntry(creature_id="a", roll=2, modifier=0, total=2, dex=10),
        ],
    )


def test_encounter_events_assign_state() -> None:
    state = _state()
    started = EncounterStarted(encounter=_encounter())
    apply(state, started)
    enc = state.encounter
    assert enc is not None and enc is not started.encounter
    eco = TurnEconomy(action=True, bonus_action=True, movement_left=30)
    apply(state, TurnStarted(creature_id="b", round=1, active_index=0, economy=eco))
    assert (enc.active_id(), enc.combatant("b").economy) == ("b", eco)
    spent = eco.model_copy(update={"action": False})
    apply(state, EconomyChanged(creature_id="b", economy=spent, reason="action"))
    assert enc.combatant("b").economy == spent
    apply(state, TurnEnded(creature_id="b"))
    assert enc.active_id() is None
    apply(state, CombatantWithdrew(creature_id="b", reason=WithdrawReason.SURRENDERED))
    assert enc.combatant("b").withdrawn is WithdrawReason.SURRENDERED
    apply(state, EncounterEnded(status=EncounterStatus.VICTORY))
    assert enc.status is EncounterStatus.VICTORY
    assert state.event_count == 6
    apply(state, EncounterStarted(encounter=_encounter()))  # a finished fight is replaced
    assert state.encounter is not enc


def test_encounter_events_that_do_not_fit_raise() -> None:
    state = _state()
    eco = TurnEconomy()
    with pytest.raises(ReducerError, match="no active encounter"):
        apply(state, TurnStarted(creature_id="a", round=1, active_index=0, economy=eco))
    unknown = _encounter()
    unknown.combatants["z"] = Combatant(creature_id="z", side=Side.NEUTRAL, zone_id="wall")
    with pytest.raises(ReducerError, match="unknown creatures"):
        apply(state, EncounterStarted(encounter=unknown))
    apply(state, EncounterStarted(encounter=_encounter()))
    with pytest.raises(ReducerError, match="already active"):
        apply(state, EncounterStarted(encounter=_encounter()))
    with pytest.raises(ReducerError, match="not at initiative index"):
        apply(state, TurnStarted(creature_id="a", round=1, active_index=0, economy=eco))
    with pytest.raises(ReducerError, match="out of range"):
        apply(state, TurnStarted(creature_id="a", round=1, active_index=5, economy=eco))
    with pytest.raises(ReducerError, match="no open turn"):
        apply(state, TurnEnded(creature_id="a"))
    with pytest.raises(ReducerError, match="not in the encounter"):
        apply(state, EconomyChanged(creature_id="q", economy=eco))
    assert state.event_count == 1
