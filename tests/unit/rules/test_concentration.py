"""Concentration tests (aidm.rules.concentration), SRD 5.1 "Concentration"."""

from __future__ import annotations

import pytest

from aidm.models.abilities import Ability
from aidm.models.conditions import ConditionLink
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.events import (
    AnyEvent,
    CheckResolved,
    ConcentrationEnded,
    ConditionRemoved,
    CreatureAdded,
    DamageTaken,
)
from aidm.models.state import ActiveCondition, Creature, CreatureKind, GameState
from aidm.rules.concentration import (
    concentration_after_damage,
    concentration_dc,
    concentration_upkeep,
    end_concentration,
    start_concentration,
)
from aidm.rules.condition_timing import new_condition
from aidm.rules.damage import resolve_damage
from aidm.session.reducer import apply


class FixedRng:
    def __init__(self, value: int) -> None:
        self.value = value

    def randint(self, a: int, b: int, /) -> int:
        return self.value


def make(cid: str, hp: int = 30, *conds: ActiveCondition) -> Creature:
    return Creature(
        id=cid,
        name=cid.upper(),
        kind=CreatureKind.PC,
        max_hp=30,
        hp=hp,
        abilities={a: 10 for a in Ability},
        conditions=list(conds),
    )


def setup() -> GameState:
    state = GameState(campaign_id="t", seed=1)
    held = new_condition("paralyzed", source_id="cleric", rounds=10)
    for c in (make("cleric"), make("orc", 30, held), make("ally")):
        apply(state, CreatureAdded(creature=c))
    link = ConditionLink(creature_id="orc", name="paralyzed")
    run(state, start_concentration(state, "cleric", "hold-person", [link]))
    return state


def run(state: GameState, events: list[AnyEvent]) -> GameState:
    for event in events:
        apply(state, event)
    return state


@pytest.mark.parametrize(("damage", "dc"), [(0, 10), (5, 10), (21, 10), (22, 11), (45, 22)])
def test_golden_concentration_dc(damage: int, dc: int) -> None:
    # SRD 5.1: DC 10 or half the damage taken, whichever is higher.
    assert concentration_dc(damage) == dc


def test_concentration_dc_rejects_negative() -> None:
    with pytest.raises(ValueError):
        concentration_dc(-1)


def test_start_records_concentration() -> None:
    state = setup()
    conc = state.creatures["cleric"].concentrating_on
    assert conc is not None
    assert conc.spell_id == "hold-person"


def test_new_concentration_ends_old_and_its_conditions() -> None:
    state = setup()
    events = start_concentration(state, "cleric", "bless")
    assert events[0] == ConditionRemoved(
        creature_id="orc", name="paralyzed", source_id="cleric", exact_source=True
    )
    assert isinstance(events[1], ConcentrationEnded)
    run(state, events)
    assert state.creatures["orc"].conditions == []
    conc = state.creatures["cleric"].concentrating_on
    assert conc is not None and conc.spell_id == "bless"


def test_start_unknown_caster_raises() -> None:
    with pytest.raises(ValueError):
        start_concentration(setup(), "ghost", "bless")


def test_end_skips_missing_targets_and_conditions() -> None:
    state = setup()
    state.creatures["orc"].conditions = []
    assert end_concentration(state, "cleric", "x") == [
        ConcentrationEnded(creature_id="cleric", spell_id="hold-person", reason="x")
    ]
    del state.creatures["orc"]
    assert len(end_concentration(state, "cleric", "x")) == 1
    assert end_concentration(state, "ally", "x") == []
    assert end_concentration(state, "ghost", "x") == []


def _hit(state: GameState, cid: str, amount: int) -> DamageTaken:
    events = resolve_damage(
        state.creatures[cid], [DamagePacket(amount=amount, damage_type=DamageType.FIRE)]
    )
    run(state, events)
    first = events[0]
    assert isinstance(first, DamageTaken)
    return first


def test_damage_forces_con_save_and_success_keeps_it() -> None:
    state = setup()
    taken = _hit(state, "cleric", 24)
    events = concentration_after_damage(FixedRng(12), state, taken)
    assert len(events) == 1
    check = events[0]
    assert isinstance(check, CheckResolved)
    assert (check.result.ability, check.result.dc, check.result.success) == (Ability.CON, 12, True)


def test_failed_save_ends_concentration_and_linked_conditions() -> None:
    state = setup()
    taken = _hit(state, "cleric", 8)
    events = concentration_after_damage(FixedRng(9), state, taken)
    run(state, events)
    assert state.creatures["cleric"].concentrating_on is None
    assert state.creatures["orc"].conditions == []


def test_zero_damage_and_non_concentrators_need_no_save() -> None:
    state = setup()
    state.creatures["cleric"].immunities = [DamageType.FIRE]
    assert concentration_after_damage(FixedRng(1), state, _hit(state, "cleric", 10)) == []
    assert concentration_after_damage(FixedRng(1), state, _hit(state, "ally", 10)) == []


def test_dropping_to_zero_breaks_concentration_without_roll() -> None:
    state = setup()
    taken = _hit(state, "cleric", 30)
    events = concentration_after_damage(FixedRng(20), state, taken)
    assert not any(isinstance(e, CheckResolved) for e in events)
    assert events[-1] == ConcentrationEnded(
        creature_id="cleric", spell_id="hold-person", reason="incapacitated"
    )


def test_upkeep_on_death_and_stun() -> None:
    state = setup()
    assert concentration_upkeep(state, "cleric") == []
    assert concentration_upkeep(state, "ally") == []
    state.creatures["cleric"].conditions = [ActiveCondition(name="stunned")]
    assert isinstance(concentration_upkeep(state, "cleric")[-1], ConcentrationEnded)
    state.creatures["cleric"].dead = True
    ended = concentration_upkeep(state, "cleric")[-1]
    assert isinstance(ended, ConcentrationEnded) and ended.reason == "died"
