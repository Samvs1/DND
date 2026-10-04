"""Unit tests for aidm.session.reducer and the event models."""

from __future__ import annotations

import random
import typing

import pytest
from pydantic import ValidationError

from aidm.models.abilities import Ability
from aidm.models.events import (
    EVENT_TYPES,
    AnyEvent,
    ConditionApplied,
    ConditionRemoved,
    CreatureAdded,
    CreatureDied,
    CreatureRemoved,
    DeathSaveRolled,
    DiceRolled,
    HpChanged,
    LoggedEvent,
    Stabilized,
    TempHpSet,
    event_adapter,
)
from aidm.models.state import ActiveCondition, Creature, CreatureKind, GameState
from aidm.rules.d20 import roll_d20
from aidm.rules.dice import roll
from aidm.session.reducer import ReducerError, apply, replay


def make_state() -> GameState:
    return GameState(campaign_id="c1", seed=7)


def goblin(cid: str = "gob1") -> Creature:
    return Creature(id=cid, name="Goblin", kind=CreatureKind.MONSTER, max_hp=7, hp=7, ac=15)


def test_creature_defaults() -> None:
    c = goblin()
    assert c.abilities == dict.fromkeys(Ability, 10)
    assert (c.temp_hp, c.conditions, c.stable, c.dead) == (0, [], False, False)


def test_creature_hp_above_max_rejected() -> None:
    with pytest.raises(ValidationError):
        Creature(id="x", name="X", kind=CreatureKind.PC, max_hp=5, hp=6)


def test_add_hp_temp_and_count() -> None:
    state = make_state()
    apply(state, CreatureAdded(creature=goblin()))
    apply(state, HpChanged(creature_id="gob1", delta=-5, new_hp=2))
    apply(state, TempHpSet(creature_id="gob1", temp_hp=4))
    c = state.creatures["gob1"]
    assert (c.hp, c.temp_hp, state.event_count) == (2, 4, 3)


def test_apply_returns_same_object() -> None:
    state = make_state()
    assert apply(state, CreatureAdded(creature=goblin())) is state


def test_added_creature_is_copied() -> None:
    event = CreatureAdded(creature=goblin())
    state = apply(make_state(), event)
    apply(state, HpChanged(creature_id="gob1", delta=-7, new_hp=0))
    assert event.creature.hp == 7


def test_duplicate_and_unknown_ids_raise() -> None:
    state = apply(make_state(), CreatureAdded(creature=goblin()))
    with pytest.raises(ReducerError):
        apply(state, CreatureAdded(creature=goblin()))
    with pytest.raises(ReducerError):
        apply(state, HpChanged(creature_id="nobody", delta=-1, new_hp=0))
    with pytest.raises(ReducerError):
        apply(state, CreatureRemoved(creature_id="nobody"))
    assert state.event_count == 1


def test_conditions_replace_by_source_and_remove() -> None:
    state = apply(make_state(), CreatureAdded(creature=goblin()))
    for source, rounds in (("a", 2), ("b", 1), ("a", 3)):
        cond = ActiveCondition(name="prone", source_id=source, rounds_left=rounds)
        apply(state, ConditionApplied(creature_id="gob1", condition=cond))
    conds = state.creatures["gob1"].conditions
    assert [(c.source_id, c.rounds_left) for c in conds] == [("b", 1), ("a", 3)]
    apply(state, ConditionRemoved(creature_id="gob1", name="prone", source_id="b"))
    assert [c.source_id for c in state.creatures["gob1"].conditions] == ["a"]
    apply(state, ConditionRemoved(creature_id="gob1", name="prone"))
    assert state.creatures["gob1"].conditions == []


def test_death_saves_stabilize_and_die() -> None:
    state = apply(make_state(), CreatureAdded(creature=goblin()))
    d20 = roll_d20(random.Random(1))
    apply(state, DeathSaveRolled(creature_id="gob1", roll=d20, successes=2, failures=1))
    c = state.creatures["gob1"]
    assert (c.death_save_successes, c.death_save_failures) == (2, 1)
    apply(state, Stabilized(creature_id="gob1"))
    assert (c.stable, c.death_save_successes, c.death_save_failures) == (True, 0, 0)
    apply(state, CreatureDied(creature_id="gob1"))
    assert (c.dead, c.stable) == (True, False)


def test_dice_rolled_only_counts() -> None:
    state = apply(make_state(), CreatureAdded(creature=goblin()))
    before = state.model_dump()
    apply(state, DiceRolled(roll=roll("2d6+1", random.Random(3)), roller_id="gob1"))
    after = state.model_dump()
    assert after.pop("event_count") == before.pop("event_count") + 1
    assert after == before


def test_remove_creature() -> None:
    state = apply(make_state(), CreatureAdded(creature=goblin()))
    apply(state, CreatureRemoved(creature_id="gob1"))
    assert state.creatures == {}


def test_replay_leaves_initial_untouched() -> None:
    initial = make_state()
    final = replay(initial, [CreatureAdded(creature=goblin())])
    assert initial.creatures == {}
    assert initial.event_count == 0
    assert "gob1" in final.creatures


def test_event_types_match_union() -> None:
    members = typing.get_args(AnyEvent.__value__)
    assert set(members) == set(EVENT_TYPES)
    tags = [t.model_fields["type"].default for t in EVENT_TYPES]
    assert len(set(tags)) == len(tags)


def test_unknown_event_tag_rejected() -> None:
    with pytest.raises(ValidationError):
        event_adapter.validate_json('{"type": "nope", "creature_id": "x"}')


def test_events_are_frozen_and_strict() -> None:
    event = TempHpSet(creature_id="a", temp_hp=1)
    field = "temp_hp"
    with pytest.raises(ValidationError):
        setattr(event, field, 3)
    with pytest.raises(ValidationError):
        TempHpSet.model_validate({"creature_id": "a", "temp_hp": 1, "bogus": 1})


def test_logged_event_round_trip() -> None:
    entry = LoggedEvent(seq=4, event=HpChanged(creature_id="a", delta=-2, new_hp=3))
    assert LoggedEvent.model_validate_json(entry.model_dump_json()) == entry


def test_condition_ticked_and_exact_removal() -> None:
    from aidm.models.events import ConditionTicked

    state = make_state()
    apply(state, CreatureAdded(creature=goblin()))
    timed = ActiveCondition(name="prone", rounds_left=3)
    lasting = ActiveCondition(name="prone", source_id="trap")
    apply(state, ConditionApplied(creature_id="gob1", condition=timed))
    apply(state, ConditionApplied(creature_id="gob1", condition=lasting))
    apply(state, ConditionTicked(creature_id="gob1", name="prone", rounds_left=2))
    assert state.creatures["gob1"].conditions[0].rounds_left == 2
    with pytest.raises(ReducerError):
        apply(
            state,
            ConditionTicked(creature_id="gob1", name="prone", source_id="trap", rounds_left=1),
        )
    apply(state, ConditionRemoved(creature_id="gob1", name="prone", exact_source=True))
    assert [c.source_id for c in state.creatures["gob1"].conditions] == ["trap"]


def test_concentration_started_and_ended() -> None:
    from aidm.models.conditions import Concentration
    from aidm.models.events import ConcentrationEnded, ConcentrationStarted

    state = make_state()
    apply(state, CreatureAdded(creature=goblin()))
    conc = Concentration(spell_id="bless")
    apply(state, ConcentrationStarted(creature_id="gob1", concentration=conc))
    assert state.creatures["gob1"].concentrating_on == conc
    apply(state, ConcentrationEnded(creature_id="gob1", spell_id="bless"))
    assert state.creatures["gob1"].concentrating_on is None


def test_resources_and_party_pool() -> None:
    from aidm.models.events import CampSuppliesChanged, LongRestTaken, ResourceSet, ShortRestTaken
    from aidm.models.state import RechargeKind, Resource

    state = make_state()
    apply(state, CreatureAdded(creature=goblin()))
    res = Resource(current=1, maximum=2, recharge=RechargeKind.SHORT_REST)
    apply(state, ResourceSet(creature_id="gob1", key="ki", resource=res))
    assert state.creatures["gob1"].resources == {"ki": res}
    apply(state, CampSuppliesChanged(delta=50, camp_supplies=50))
    apply(state, ShortRestTaken(short_rests_used=2))
    assert (state.camp_supplies, state.short_rests_used) == (50, 2)
    apply(state, LongRestTaken(supplies_spent=40, camp_supplies=10))
    assert (state.camp_supplies, state.short_rests_used) == (10, 0)
