"""Condition lifecycle tests (aidm.rules.condition_timing): durations, save-ends, combat end."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aidm.data.registry import UnknownEntryError
from aidm.models.abilities import Ability
from aidm.models.conditions import ConditionDuration, SaveEnds, TurnBoundary
from aidm.models.events import (
    AnyEvent,
    CheckResolved,
    ConditionApplied,
    ConditionRemoved,
    ConditionTicked,
    CreatureAdded,
)
from aidm.models.state import ActiveCondition, Creature, CreatureKind, GameState
from aidm.rules.condition_timing import (
    apply_condition,
    combat_end_events,
    long_rest_condition_events,
    new_condition,
    remove_condition,
    turn_end_events,
    turn_start_events,
)
from aidm.session.reducer import apply


class FixedRng:
    def __init__(self, value: int) -> None:
        self.value = value

    def randint(self, a: int, b: int, /) -> int:
        return self.value


def make(cid: str, *conds: ActiveCondition) -> Creature:
    return Creature(
        id=cid, name=cid.upper(), kind=CreatureKind.PC, max_hp=10, hp=10, conditions=list(conds)
    )


def state_of(*creatures: Creature) -> GameState:
    state = GameState(campaign_id="t", seed=1)
    for c in creatures:
        apply(state, CreatureAdded(creature=c))
    return state


def run(state: GameState, events: list[AnyEvent]) -> GameState:
    for event in events:
        apply(state, event)
    return state


def names(state: GameState, cid: str) -> list[str]:
    return [c.name for c in state.creatures[cid].conditions]


def test_new_condition_defaults_from_data() -> None:
    plain = new_condition("prone")
    assert plain.duration is ConditionDuration.UNTIL_REMOVED
    assert plain.rounds_left is None
    exhausted = new_condition("exhaustion")
    assert exhausted.duration is ConditionDuration.UNTIL_LONG_REST
    dodge = new_condition("dodging", source_id="a")
    assert (dodge.duration, dodge.rounds_left, dodge.tick_on) == (
        ConditionDuration.ROUNDS,
        1,
        TurnBoundary.START_OF_TURN,
    )


def test_new_condition_effect_overrides() -> None:
    held = new_condition(
        "paralyzed",
        source_id="mage",
        rounds=10,
        save_ends=SaveEnds(ability=Ability.WIS, dc=13),
    )
    assert (held.duration, held.rounds_left) == (ConditionDuration.ROUNDS, 10)
    assert held.save_ends is not None
    rest = new_condition("poisoned", until_long_rest=True)
    assert rest.duration is ConditionDuration.UNTIL_LONG_REST
    with pytest.raises(UnknownEntryError):
        new_condition("nope")


def test_active_condition_duration_consistency() -> None:
    assert ActiveCondition(name="prone", rounds_left=2).duration is ConditionDuration.ROUNDS
    with pytest.raises(ValidationError):
        ActiveCondition(name="prone", duration=ConditionDuration.ROUNDS)
    with pytest.raises(ValidationError):
        ActiveCondition(name="prone", duration=ConditionDuration.UNTIL_REMOVED, rounds_left=1)


def test_apply_respects_immunity_and_death() -> None:
    target = make("t")
    cond = new_condition("poisoned", source_id="x")
    assert apply_condition(target, cond) == [ConditionApplied(creature_id="t", condition=cond)]
    immune = make("t")
    immune.condition_immunities = ["poisoned"]
    assert apply_condition(immune, cond) == []
    dead = make("t")
    dead.dead = True
    assert apply_condition(dead, cond) == []
    with pytest.raises(UnknownEntryError):
        apply_condition(target, ActiveCondition(name="nope"))


def test_remove_condition_only_when_present() -> None:
    target = make("t", ActiveCondition(name="prone", source_id="a"))
    assert remove_condition(target, "poisoned") == []
    assert remove_condition(target, "prone", "b") == []
    assert remove_condition(target, "prone") == [ConditionRemoved(creature_id="t", name="prone")]


def test_rounds_tick_on_own_turn_end_and_expire() -> None:
    state = state_of(make("t", new_condition("poisoned", source_id="x", rounds=2)))
    events = turn_end_events(FixedRng(10), state, "t")
    assert events == [
        ConditionTicked(creature_id="t", name="poisoned", source_id="x", rounds_left=1)
    ]
    run(state, events)
    assert turn_start_events(state, "t") == []
    run(state, turn_end_events(FixedRng(10), state, "t"))
    assert names(state, "t") == []


def test_tick_on_source_turn_start() -> None:
    # "until the start of the caster's next turn": ticks on the caster's turn, not the bearer's.
    cond = new_condition(
        "frightened",
        source_id="c",
        rounds=1,
        tick_on=TurnBoundary.START_OF_TURN,
        tick_creature_id="c",
    )
    state = state_of(make("t", cond), make("c"))
    assert turn_start_events(state, "t") == []
    run(state, turn_start_events(state, "c"))
    assert names(state, "t") == []


def test_exact_expiry_keeps_other_sources() -> None:
    timed = new_condition("prone", rounds=1)
    lasting = new_condition("prone", source_id="trap")
    state = state_of(make("t", timed, lasting))
    run(state, turn_end_events(FixedRng(10), state, "t"))
    assert [(c.name, c.source_id) for c in state.creatures["t"].conditions] == [("prone", "trap")]


def test_save_ends_success_removes_without_tick() -> None:
    save = SaveEnds(ability=Ability.WIS, dc=13)
    held = new_condition("paralyzed", source_id="mage", rounds=10, save_ends=save)
    state = state_of(make("t", held))
    events = turn_end_events(FixedRng(15), state, "t")
    assert isinstance(events[0], CheckResolved)
    assert events[0].result.success
    assert events[1:] == [
        ConditionRemoved(creature_id="t", name="paralyzed", source_id="mage", exact_source=True)
    ]


def test_save_ends_failure_ticks() -> None:
    save = SaveEnds(ability=Ability.WIS, dc=13)
    held = new_condition("paralyzed", source_id="mage", rounds=10, save_ends=save)
    state = state_of(make("t", held))
    events = turn_end_events(FixedRng(2), state, "t")
    assert isinstance(events[0], CheckResolved)
    assert not events[0].result.success
    assert events[1] == ConditionTicked(
        creature_id="t", name="paralyzed", source_id="mage", rounds_left=9
    )


def test_dead_bearers_do_not_tick_or_save() -> None:
    save = SaveEnds(ability=Ability.WIS, dc=13)
    corpse = make("t", new_condition("poisoned", rounds=1, save_ends=save))
    corpse.dead = True
    state = state_of(corpse)
    assert turn_end_events(FixedRng(20), state, "t") == []
    assert turn_end_events(FixedRng(20), state, "missing") == []


def test_v1_conditions_persist_after_combat() -> None:
    # v1 wiped every condition when combat ended. Only round-based durations expire;
    # until-long-rest and until-removed conditions (and the 0-HP unconscious state) persist.
    fighter = make(
        "f",
        new_condition("poisoned", source_id="spider", rounds=3),
        new_condition("exhaustion"),
        new_condition("frightened", source_id="curse"),
    )
    downed = make("d", ActiveCondition(name="unconscious", source_id="zero_hp"))
    state = state_of(fighter, downed)
    assert not fighter.conditions[0].persists_after_combat
    assert fighter.conditions[1].persists_after_combat
    run(state, combat_end_events(state))
    assert names(state, "f") == ["exhaustion", "frightened"]
    assert names(state, "d") == ["unconscious"]


def test_long_rest_ends_rounds_and_until_long_rest_only() -> None:
    target = make(
        "t",
        new_condition("poisoned", rounds=3),
        new_condition("exhaustion"),
        new_condition("charmed", source_id="vampire"),
    )
    state = state_of(target)
    run(state, long_rest_condition_events(state.creatures["t"]))
    assert names(state, "t") == ["charmed"]
