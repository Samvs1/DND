"""Hypothesis helpers that draw events valid for the current state (shared by property tests)."""

from __future__ import annotations

import random
from collections.abc import Callable

from hypothesis import strategies as st

from aidm.models.abilities import Ability
from aidm.models.events import (
    AnyEvent,
    ConditionApplied,
    ConditionRemoved,
    CreatureAdded,
    CreatureDied,
    CreatureRemoved,
    DeathSaveRolled,
    DiceRolled,
    HpChanged,
    Stabilized,
    TempHpSet,
)
from aidm.models.state import ActiveCondition, Creature, CreatureKind, GameState
from aidm.rules.d20 import roll_d20
from aidm.rules.dice import roll

CONDITIONS = ["prone", "poisoned", "frightened", "blinded"]
SOURCES = [None, "src1", "src2"]
NAMES = st.text(alphabet="abcdefghijklmnopqrstuvwxyz '-", min_size=1, max_size=12)


def _creature(data: st.DataObject, cid: str) -> Creature:
    max_hp = data.draw(st.integers(min_value=1, max_value=200))
    scores = data.draw(st.lists(st.integers(1, 30), min_size=6, max_size=6))
    return Creature(
        id=cid,
        name=data.draw(NAMES),
        kind=data.draw(st.sampled_from(list(CreatureKind))),
        abilities=dict(zip(Ability, scores, strict=True)),
        max_hp=max_hp,
        hp=data.draw(st.integers(min_value=0, max_value=max_hp)),
        ac=data.draw(st.integers(min_value=5, max_value=25)),
    )


def _hp(data: st.DataObject, c: Creature) -> AnyEvent:
    new_hp = data.draw(st.integers(min_value=0, max_value=c.max_hp))
    return HpChanged(creature_id=c.id, delta=new_hp - c.hp, new_hp=new_hp)


def _temp(data: st.DataObject, c: Creature) -> AnyEvent:
    return TempHpSet(creature_id=c.id, temp_hp=data.draw(st.integers(0, 50)))


def _cond_on(data: st.DataObject, c: Creature) -> AnyEvent:
    cond = ActiveCondition(
        name=data.draw(st.sampled_from(CONDITIONS)),
        source_id=data.draw(st.sampled_from(SOURCES)),
        rounds_left=data.draw(st.one_of(st.none(), st.integers(0, 10))),
    )
    return ConditionApplied(creature_id=c.id, condition=cond)


def _cond_off(data: st.DataObject, c: Creature) -> AnyEvent:
    return ConditionRemoved(
        creature_id=c.id,
        name=data.draw(st.sampled_from(CONDITIONS)),
        source_id=data.draw(st.sampled_from(SOURCES)),
    )


def _death_save(data: st.DataObject, c: Creature) -> AnyEvent:
    d20 = roll_d20(random.Random(data.draw(st.integers(0, 10_000))))
    return DeathSaveRolled(
        creature_id=c.id,
        roll=d20,
        successes=data.draw(st.integers(0, 3)),
        failures=data.draw(st.integers(0, 3)),
    )


def _dice(data: st.DataObject, c: Creature) -> AnyEvent:
    expr = data.draw(st.sampled_from(["1d20+5", "2d6+3", "8d6", "4d6kh3", "1d4-1"]))
    rolled = roll(expr, random.Random(data.draw(st.integers(0, 10_000))))
    return DiceRolled(roll=rolled, roller_id=c.id, label=data.draw(NAMES))


TARGETED: list[Callable[[st.DataObject, Creature], AnyEvent]] = [
    _hp,
    _temp,
    _cond_on,
    _cond_off,
    _death_save,
    _dice,
    lambda _d, c: Stabilized(creature_id=c.id),
    lambda _d, c: CreatureDied(creature_id=c.id),
    lambda _d, c: CreatureRemoved(creature_id=c.id),
]


def draw_event(data: st.DataObject, state: GameState, next_id: int) -> AnyEvent:
    """Draw one event that is valid for `state` (adds a creature when there are none)."""
    if not state.creatures or data.draw(st.integers(0, 5)) == 0:
        return CreatureAdded(creature=_creature(data, f"c{next_id}"))
    target = state.creatures[data.draw(st.sampled_from(sorted(state.creatures)))]
    return data.draw(st.sampled_from(TARGETED))(data, target)
