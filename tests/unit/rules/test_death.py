"""Golden tests for death saving throws and stabilising (aidm.rules.death).

SRD 5.1 (CC-BY-4.0) "Death Saving Throws" and "Stabilizing a Creature".
"""

from __future__ import annotations

import pytest

from aidm.models.abilities import Ability, Skill
from aidm.models.events import (
    AnyEvent,
    CheckResolved,
    ConditionRemoved,
    CreatureDied,
    DeathSaveRolled,
    HpChanged,
    Stabilized,
)
from aidm.models.state import ActiveCondition, Creature, CreatureKind
from aidm.rules.damage import UNCONSCIOUS, ZERO_HP_SOURCE
from aidm.rules.death import is_dying, medicine_stabilize, roll_death_save, stabilize


class ScriptedRng:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def randint(self, a: int, b: int, /) -> int:
        assert (a, b) == (1, 20)
        return self.values.pop(0)


DOWN = ActiveCondition(name=UNCONSCIOUS, source_id=ZERO_HP_SOURCE)


def dying(successes: int = 0, failures: int = 0) -> Creature:
    return Creature(
        id="pc",
        name="Hero",
        kind=CreatureKind.PC,
        max_hp=20,
        hp=0,
        conditions=[DOWN],
        death_save_successes=successes,
        death_save_failures=failures,
    )


def healer() -> Creature:
    return Creature(
        id="cleric",
        name="Cleric",
        kind=CreatureKind.PC,
        max_hp=10,
        hp=10,
        abilities={**dict.fromkeys(Ability, 10), Ability.WIS: 14},
        skill_proficiencies=[Skill.MEDICINE],
    )


def counters(events: list[AnyEvent]) -> tuple[int, int]:
    first = events[0]
    assert isinstance(first, DeathSaveRolled)
    return first.successes, first.failures


def test_golden_save_success_and_failure() -> None:
    # SRD 5.1: 10 or higher succeeds, below 10 fails.
    assert counters(roll_death_save(ScriptedRng([10]), dying())) == (1, 0)
    assert counters(roll_death_save(ScriptedRng([9]), dying())) == (0, 1)
    assert counters(roll_death_save(ScriptedRng([9]), dying(), bonus=1)) == (1, 0)


def test_golden_nat1_two_failures_and_death() -> None:
    # SRD 5.1: a natural 1 counts as two failures; the third failure kills.
    assert counters(roll_death_save(ScriptedRng([1]), dying())) == (0, 2)
    events = roll_death_save(ScriptedRng([1]), dying(failures=2))
    assert counters(events) == (0, 3) and events[-1] == CreatureDied(creature_id="pc")
    events = roll_death_save(ScriptedRng([5]), dying(successes=2, failures=2))
    assert events[-1] == CreatureDied(creature_id="pc")


def test_golden_nat20_regains_one_hp() -> None:
    # SRD 5.1: a natural 20 regains 1 hit point (and ends dying).
    events = roll_death_save(ScriptedRng([20]), dying(successes=1, failures=2))
    assert counters(events) == (0, 0)
    assert events[1:] == [
        HpChanged(creature_id="pc", delta=1, new_hp=1),
        ConditionRemoved(creature_id="pc", name=UNCONSCIOUS, source_id=ZERO_HP_SOURCE),
    ]


def test_golden_three_successes_stable() -> None:
    # SRD 5.1: on the third success the creature becomes stable.
    events = roll_death_save(ScriptedRng([15]), dying(successes=2))
    assert events[-1] == Stabilized(creature_id="pc")


def test_not_dying_cannot_roll() -> None:
    stable = dying().model_copy(update={"stable": True})
    assert not is_dying(stable)
    with pytest.raises(ValueError):
        roll_death_save(ScriptedRng([10]), stable)
    monster = dying().model_copy(update={"kind": CreatureKind.MONSTER})
    assert not is_dying(monster)


def test_stabilize_effect() -> None:
    assert stabilize(dying()) == [Stabilized(creature_id="pc")]
    assert stabilize(dying().model_copy(update={"hp": 3})) == []


def test_golden_medicine_dc10() -> None:
    # SRD 5.1 Stabilizing a Creature: a DC 10 Wisdom (Medicine) check.
    ok = medicine_stabilize(ScriptedRng([6]), healer(), dying())  # 6 + 2 WIS + 2 prof = 10
    assert isinstance(ok[0], CheckResolved) and ok[0].result.dc == 10
    assert ok[1:] == [Stabilized(creature_id="pc")]
    fail = medicine_stabilize(ScriptedRng([5]), healer(), dying())
    assert len(fail) == 1 and isinstance(fail[0], CheckResolved)
    assert not fail[0].result.success
    assert medicine_stabilize(ScriptedRng([]), healer(), healer()) == []
