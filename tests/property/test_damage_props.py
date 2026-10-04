"""Properties of the damage choke point, healing and death saves (SPEC 7.1, 13).

Invariants: damage taken is never negative, HP stays within [0, max], temp HP never goes
negative, resistance never increases damage, and replaying the produced events (including
DamageTaken / DeathSavesSet) reproduces the live state.
"""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.models.damage import DamagePacket, DamageType
from aidm.models.events import AnyEvent, CreatureAdded, DamageTaken, HpChanged
from aidm.models.state import Creature, GameState
from aidm.rules.damage import damage_after_defenses, resolve_damage, resolve_healing
from aidm.rules.death import is_dying, medicine_stabilize, roll_death_save, stabilize
from aidm.rules.hp import gain_temp_hp
from aidm.session.reducer import apply, replay
from tests.property.event_strategies import draw_creature

PACKETS = st.lists(
    st.builds(
        DamagePacket,
        amount=st.integers(-5, 120),
        damage_type=st.sampled_from(list(DamageType)),
    ),
    min_size=1,
    max_size=4,
)


def _check_invariants(c: Creature) -> None:
    assert 0 <= c.hp <= c.max_hp
    assert c.temp_hp >= 0
    assert 0 <= c.death_save_successes <= 3
    assert 0 <= c.death_save_failures <= 3


@settings(max_examples=200)
@given(st.data(), PACKETS, st.booleans())
def test_single_hit_invariants(
    data: st.DataObject, packets: list[DamagePacket], crit: bool
) -> None:
    target = draw_creature(data, "t")
    state = GameState(campaign_id="p", seed=0)
    apply(state, CreatureAdded(creature=target))
    events = resolve_damage(target, packets, crit=crit)
    for event in events:
        apply(state, event)
        if isinstance(event, HpChanged):
            assert event.delta <= 0
    after = state.creatures["t"]
    _check_invariants(after)
    assert after.hp <= target.hp
    if events:
        log = events[0]
        assert isinstance(log, DamageTaken)
        assert log.total >= 0 and all(p.taken >= 0 for p in log.parts)
        assert log.temp_absorbed + log.hp_lost <= log.total
        assert target.hp - after.hp == log.hp_lost


@given(st.data(), PACKETS)
def test_resistance_never_increases_damage(
    data: st.DataObject, packets: list[DamagePacket]
) -> None:
    target = draw_creature(data, "t")
    for packet in packets:
        plain = target.model_copy(update={"resistances": []})
        resisted = target.model_copy(update={"resistances": [packet.damage_type]})
        assert damage_after_defenses(resisted, packet) <= damage_after_defenses(plain, packet)
        assert damage_after_defenses(target, packet) >= 0


def _step(rng: random.Random, c: Creature, op: int, amount: int) -> list[AnyEvent]:
    if op == 0:
        kind = rng.choice(list(DamageType))
        return resolve_damage(
            c, [DamagePacket(amount=amount, damage_type=kind)], crit=amount % 2 == 0
        )
    if op == 1:
        return resolve_healing(c, amount // 4)
    if op == 2:
        return gain_temp_hp(c, amount // 8)
    if op == 3 and is_dying(c):
        return roll_death_save(rng, c)
    if op == 4:
        return stabilize(c)
    return medicine_stabilize(rng, c, c) if is_dying(c) else []


@settings(max_examples=150)
@given(st.data(), st.lists(st.tuples(st.integers(0, 5), st.integers(0, 60)), max_size=30))
def test_sequences_stay_in_bounds_and_replay(
    data: st.DataObject, ops: list[tuple[int, int]]
) -> None:
    rng = random.Random(data.draw(st.integers(0, 10_000)))
    initial = GameState(campaign_id="p", seed=0)
    live = initial.model_copy(deep=True)
    log: list[AnyEvent] = [CreatureAdded(creature=draw_creature(data, "t"))]
    apply(live, log[0])
    for op, amount in ops:
        for event in _step(rng, live.creatures["t"], op, amount):
            apply(live, event)
            log.append(event)
        _check_invariants(live.creatures["t"])
    assert replay(initial, log).model_dump() == live.model_dump()
