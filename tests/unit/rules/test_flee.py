"""Flee (M3.10; M20.4, playtest 3: the ranger was told "disengage first", disengaged, and still
could not flee, three rounds running, while his downed friend died)."""

import random

import pytest

from aidm.models.commands import DisengageCommand, FleeCommand, RefusalCode
from aidm.models.encounter import Side
from aidm.models.encounter_events import CombatantWithdrew
from aidm.models.state import GameState
from aidm.rules.command_checks import CommandRefused
from tests.unit.rules.combat_fixtures import do, economy, fight, monster

RNG = random.Random(1)


def _state(foe_zone: str = "gate") -> GameState:
    hero = monster("hero", hp=20)
    return fight([(hero, Side.PARTY, "gate"), (monster("wolf"), Side.HOSTILE, foe_zone)])


def test_flee_with_a_foe_in_your_zone_needs_disengage() -> None:
    state = _state()
    with pytest.raises(CommandRefused) as refused:
        do(state, FleeCommand(actor_id="hero"), RNG)
    assert refused.value.code is RefusalCode.ENGAGED
    assert "Disengage first" in refused.value.reason


def test_flee_after_disengage_works_and_costs_no_action() -> None:
    state = _state()
    do(state, DisengageCommand(actor_id="hero"), RNG)
    assert economy(state, "hero").action is False
    events = do(state, FleeCommand(actor_id="hero"), RNG)
    assert any(isinstance(e, CombatantWithdrew) for e in events)


def test_flee_from_a_quiet_zone_keeps_the_action() -> None:
    state = _state(foe_zone="wall")
    events = do(state, FleeCommand(actor_id="hero"), RNG)
    assert any(isinstance(e, CombatantWithdrew) for e in events)
    assert economy(state, "hero").action is True and economy(state, "hero").movement_left == 0
