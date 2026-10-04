"""Properties for rests and condition durations (SPEC 7.1, 7.2, 13)."""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.models.events import CreatureAdded
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.condition_timing import combat_end_events, new_condition, turn_end_events
from aidm.rules.rests import (
    MAX_SHORT_RESTS,
    RestRefused,
    adjust_camp_supplies,
    long_rest,
    short_rest,
)
from aidm.session.reducer import apply


def _party(data: st.DataObject) -> GameState:
    state = GameState(campaign_id="p", seed=0)
    for i in range(data.draw(st.integers(1, 4))):
        max_hp = data.draw(st.integers(1, 80))
        hp = data.draw(st.integers(0, max_hp))
        creature = Creature(id=f"pc{i}", name="Hero", kind=CreatureKind.PC, max_hp=max_hp, hp=hp)
        apply(state, CreatureAdded(creature=creature))
    return state


@settings(max_examples=100)
@given(st.data())
def test_rest_sequences_keep_invariants(data: st.DataObject) -> None:
    state = _party(data)
    for _ in range(data.draw(st.integers(1, 12))):
        action = data.draw(st.sampled_from(["short", "long", "supplies"]))
        try:
            if action == "short":
                events = short_rest(state)
            elif action == "long":
                events = long_rest(state)
            else:
                events = adjust_camp_supplies(state, data.draw(st.integers(0, 60)))
        except RestRefused:
            continue
        for event in events:
            apply(state, event)
        assert 0 <= state.short_rests_used <= MAX_SHORT_RESTS
        assert state.camp_supplies >= 0
        for c in state.creatures.values():
            assert 0 <= c.hp <= c.max_hp
        if action == "long":
            assert state.short_rests_used == 0
            assert all(c.hp == c.max_hp for c in state.creatures.values())


@settings(max_examples=100)
@given(st.data())
def test_rounds_conditions_expire_after_exactly_n_turn_ends(data: st.DataObject) -> None:
    rounds = data.draw(st.integers(1, 10))
    cond = new_condition("poisoned", source_id="x", rounds=rounds)
    bearer = Creature(id="t", name="T", kind=CreatureKind.PC, max_hp=5, hp=5, conditions=[cond])
    state = GameState(campaign_id="p", seed=0)
    apply(state, CreatureAdded(creature=bearer))
    rng = random.Random(data.draw(st.integers(0, 1000)))
    for turn in range(1, rounds + 1):
        for event in turn_end_events(rng, state, "t"):
            apply(state, event)
        assert bool(state.creatures["t"].conditions) == (turn < rounds)
    assert combat_end_events(state) == []
