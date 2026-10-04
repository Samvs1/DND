"""Rest and resource tests (aidm.rules.rests, aidm.rules.resources); BG3 rest rules (SPEC 7.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aidm.models.conditions import ConditionLink
from aidm.models.events import AnyEvent, CreatureAdded, LongRestTaken, ShortRestTaken
from aidm.models.state import (
    ActiveCondition,
    Creature,
    CreatureKind,
    GameState,
    RechargeKind,
    Resource,
)
from aidm.rules.concentration import start_concentration
from aidm.rules.condition_timing import new_condition
from aidm.rules.resources import (
    ResourceError,
    define_resource,
    resource_left,
    restore_resources,
    spend_resource,
)
from aidm.rules.rests import (
    CAMP_SUPPLY_PER_MEMBER,
    MAX_SHORT_RESTS,
    RestRefusal,
    RestRefused,
    adjust_camp_supplies,
    living_party,
    long_rest,
    long_rest_cost,
    short_rest,
    short_rests_left,
)
from aidm.session.reducer import apply

PACT = "pact-slot-1"
RAGE = "rage"


def pc(cid: str, hp: int = 20, kind: CreatureKind = CreatureKind.PC) -> Creature:
    return Creature(id=cid, name=cid.upper(), kind=kind, max_hp=21, hp=hp)


def run(state: GameState, events: list[AnyEvent]) -> GameState:
    for event in events:
        apply(state, event)
    return state


def party_state(supplies: int = 100) -> GameState:
    state = GameState(campaign_id="t", seed=1)
    for c in (pc("a", 5), pc("b", 0), pc("c"), pc("orc", 3, CreatureKind.MONSTER)):
        apply(state, CreatureAdded(creature=c))
    dead = pc("d", 0)
    dead.dead = True
    apply(state, CreatureAdded(creature=dead))
    run(state, adjust_camp_supplies(state, supplies))
    a = state.creatures["a"]
    run(state, define_resource(a, PACT, 2, RechargeKind.SHORT_REST))
    run(state, define_resource(a, RAGE, 3, RechargeKind.LONG_REST))
    run(state, spend_resource(state.creatures["a"], PACT, 2))
    run(state, spend_resource(state.creatures["a"], RAGE))
    return state


def test_resource_model_bounds() -> None:
    with pytest.raises(ValidationError):
        Resource(current=3, maximum=2, recharge=RechargeKind.LONG_REST)


def test_spend_and_restore_resources() -> None:
    state = party_state()
    a = state.creatures["a"]
    assert (resource_left(a, PACT), resource_left(a, RAGE), resource_left(a, "nope")) == (0, 2, 0)
    with pytest.raises(ResourceError):
        spend_resource(a, PACT)
    with pytest.raises(ResourceError):
        spend_resource(a, "nope")
    with pytest.raises(ValueError):
        spend_resource(a, RAGE, 0)
    short_only = restore_resources(a, {RechargeKind.SHORT_REST})
    assert [getattr(e, "key", None) for e in short_only] == [PACT]
    assert len(restore_resources(a, set(RechargeKind))) == 2
    assert restore_resources(state.creatures["c"], set(RechargeKind)) == []


def test_living_party_and_cost() -> None:
    state = party_state()
    assert [c.id for c in living_party(state)] == ["a", "b", "c"]
    assert long_rest_cost(state) == 3 * CAMP_SUPPLY_PER_MEMBER


def test_adjust_camp_supplies() -> None:
    state = party_state(5)
    assert adjust_camp_supplies(state, 0) == []
    with pytest.raises(ValueError):
        adjust_camp_supplies(state, -6)
    run(state, adjust_camp_supplies(state, -5))
    assert state.camp_supplies == 0


def test_golden_short_rest_heals_half_and_short_resources() -> None:
    # BG3 short rest: regain half of max HP (21 // 2 = 10), short-rest resources recharge.
    state = party_state()
    run(state, short_rest(state))
    hp = {cid: state.creatures[cid].hp for cid in ("a", "b", "c", "d", "orc")}
    assert hp == {"a": 15, "b": 10, "c": 21, "d": 0, "orc": 3}
    assert state.creatures["b"].conditions == []
    a = state.creatures["a"]
    assert (resource_left(a, PACT), resource_left(a, RAGE)) == (2, 2)
    assert state.short_rests_used == 1


def test_short_rests_limited_between_long_rests() -> None:
    state = party_state()
    for _ in range(MAX_SHORT_RESTS):
        run(state, short_rest(state))
    assert short_rests_left(state) == 0
    with pytest.raises(RestRefused) as refused:
        short_rest(state)
    assert refused.value.reason is RestRefusal.NO_SHORT_RESTS_LEFT
    run(state, long_rest(state))
    assert short_rests_left(state) == MAX_SHORT_RESTS


def test_long_rest_refused_without_supplies() -> None:
    state = party_state(supplies=29)
    with pytest.raises(RestRefused) as refused:
        long_rest(state)
    assert refused.value.reason is RestRefusal.NOT_ENOUGH_SUPPLIES
    assert state.camp_supplies == 29


def test_rests_refused_without_living_party() -> None:
    state = GameState(campaign_id="t", seed=1)
    for rest in (short_rest, long_rest):
        with pytest.raises(RestRefused) as refused:
            rest(state)
        assert refused.value.reason is RestRefusal.NO_PARTY


def test_long_rest_full_restore() -> None:
    state = party_state()
    b = state.creatures["b"]
    b.conditions = [ActiveCondition(name="unconscious", source_id="zero_hp")]
    b.death_save_failures = 2
    c = state.creatures["c"]
    c.temp_hp = 4
    c.conditions = [new_condition("exhaustion"), new_condition("charmed", source_id="hag")]
    link = ConditionLink(creature_id="orc", name="paralyzed")
    state.creatures["orc"].conditions = [new_condition("paralyzed", source_id="a", rounds=5)]
    run(state, start_concentration(state, "a", "hold-person", [link]))
    events = long_rest(state)
    assert events[0] == LongRestTaken(supplies_spent=30, camp_supplies=70)
    assert not any(isinstance(e, ShortRestTaken) for e in events)
    run(state, events)
    for cid in ("a", "b", "c"):
        assert state.creatures[cid].hp == 21
    assert state.creatures["d"].hp == 0
    assert (b.conditions, b.death_save_failures) == ([], 0)
    assert c.temp_hp == 0
    assert [x.name for x in c.conditions] == ["charmed"]
    a = state.creatures["a"]
    assert (resource_left(a, PACT), resource_left(a, RAGE)) == (2, 3)
    assert a.concentrating_on is None
    assert state.creatures["orc"].conditions == []
    assert state.camp_supplies == 70
