"""Golden and unit tests for the damage choke point and healing (aidm.rules.damage).

Rules cited from SRD 5.1 (CC-BY-4.0): "Damage Resistance and Vulnerability", "Temporary Hit
Points", "Dropping to 0 Hit Points" (Instant Death, Damage at 0 Hit Points), "Healing".
"""

from __future__ import annotations

import pytest

from aidm.data.srd import srd
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.events import (
    AnyEvent,
    ConditionApplied,
    CreatureAdded,
    CreatureDied,
    DamageTaken,
    DeathSavesSet,
    HpChanged,
    TempHpSet,
)
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.damage import (
    UNCONSCIOUS,
    ZERO_HP_SOURCE,
    damage_after_defenses,
    resolve_damage,
    resolve_healing,
    uses_death_saves,
)
from aidm.session.reducer import apply

FIRE = DamageType.FIRE
SLASH = DamageType.SLASHING


def pkt(amount: int, kind: DamageType = SLASH) -> DamagePacket:
    return DamagePacket(amount=amount, damage_type=kind)


def pc(**kw: object) -> Creature:
    data: dict[str, object] = {"id": "pc", "name": "Hero", "kind": CreatureKind.PC}
    data.update({"max_hp": 20, "hp": 20})
    data.update(kw)
    return Creature.model_validate(data)


def run(creature: Creature, events: list[AnyEvent]) -> Creature:
    state = GameState(campaign_id="c", seed=0)
    apply(state, CreatureAdded(creature=creature))
    for event in events:
        apply(state, event)
    return state.creatures[creature.id]


def test_damage_types_match_srd() -> None:
    assert {t.value for t in DamageType} == {d.index for d in srd().damage_types.all()}
    assert len(DamageType) == 13


def test_golden_resistance_vulnerability_immunity() -> None:
    # SRD 5.1: resistance halves (round down), vulnerability doubles, immunity -> 0;
    # resistance and vulnerability both apply (halve then double).
    c = pc(resistances=[FIRE], vulnerabilities=[DamageType.COLD], immunities=[DamageType.POISON])
    assert damage_after_defenses(c, pkt(7, FIRE)) == 3
    assert damage_after_defenses(c, pkt(7, DamageType.COLD)) == 14
    assert damage_after_defenses(c, pkt(7, DamageType.POISON)) == 0
    assert damage_after_defenses(c, pkt(7)) == 7
    both = pc(resistances=[FIRE], vulnerabilities=[FIRE])
    assert damage_after_defenses(both, pkt(7, FIRE)) == 6
    assert damage_after_defenses(c, pkt(-2)) == 0


def test_mixed_packets_one_hit() -> None:
    c = pc(resistances=[FIRE])
    events = resolve_damage(c, [pkt(5), pkt(9, FIRE)], source_id="ogre")
    log = events[0]
    assert isinstance(log, DamageTaken)
    assert [p.taken for p in log.parts] == [5, 4]
    assert (log.total, log.hp_lost, log.source_id) == (9, 9, "ogre")
    assert events[1:] == [HpChanged(creature_id="pc", delta=-9, new_hp=11)]


def test_golden_temp_hp_absorb_first() -> None:
    # SRD 5.1 Temporary Hit Points: lost first, leftover carries to real HP.
    c = pc(temp_hp=5)
    events = resolve_damage(c, [pkt(8)])
    assert events[1:] == [
        TempHpSet(creature_id="pc", temp_hp=0),
        HpChanged(creature_id="pc", delta=-3, new_hp=17),
    ]
    assert run(c, events).hp == 17
    only_temp = resolve_damage(c, [pkt(4)])
    assert only_temp[1:] == [TempHpSet(creature_id="pc", temp_hp=1)]


def test_immune_damage_logs_zero_and_changes_nothing() -> None:
    c = pc(immunities=[FIRE])
    events = resolve_damage(c, [pkt(30, FIRE)])
    assert len(events) == 1 and isinstance(events[0], DamageTaken) and events[0].total == 0


def test_pc_drops_unconscious_and_dying() -> None:
    c = pc(hp=6)
    after = run(c, resolve_damage(c, [pkt(10)]))
    assert after.hp == 0 and not after.dead
    assert [(x.name, x.source_id) for x in after.conditions] == [(UNCONSCIOUS, ZERO_HP_SOURCE)]


def test_golden_instant_death() -> None:
    # SRD 5.1 Instant Death: remaining damage after 0 HP >= max HP kills outright.
    c = pc(hp=6, max_hp=12)
    assert CreatureDied(creature_id="pc") in resolve_damage(c, [pkt(18)])
    assert CreatureDied(creature_id="pc") not in resolve_damage(c, [pkt(17)])


def test_monster_dies_at_zero_unless_flagged() -> None:
    gob = Creature(id="g", name="Goblin", kind=CreatureKind.MONSTER, max_hp=7, hp=7)
    assert not uses_death_saves(gob)
    events = resolve_damage(gob, [pkt(7)])
    assert events[-1] == CreatureDied(creature_id="g")
    assert run(gob, events).dead
    boss = gob.model_copy(update={"death_saves": True})
    assert uses_death_saves(boss)
    assert isinstance(resolve_damage(boss, [pkt(7)])[-1], ConditionApplied)


def test_golden_damage_at_zero_hp_death_failures() -> None:
    # SRD 5.1 Damage at 0 Hit Points: one failure, two on a critical hit; stable is lost.
    c = pc(hp=0, stable=True, conditions=[{"name": UNCONSCIOUS, "source_id": ZERO_HP_SOURCE}])
    events = resolve_damage(c, [pkt(3)])
    assert events[-1] == DeathSavesSet(creature_id="pc", failures=1, stable=False)
    crit = resolve_damage(c, [pkt(3)], crit=True)
    assert crit[-1] == DeathSavesSet(creature_id="pc", failures=2)
    two = c.model_copy(update={"death_save_failures": 2, "stable": False})
    assert resolve_damage(two, [pkt(1)])[-1] == CreatureDied(creature_id="pc")
    assert resolve_damage(c, [pkt(20)])[-1] == CreatureDied(creature_id="pc")


def test_temp_hp_at_zero_prevents_failure() -> None:
    c = pc(hp=0, temp_hp=5)
    events = resolve_damage(c, [pkt(4)])
    assert not any(isinstance(e, DeathSavesSet | CreatureDied) for e in events)


def test_dead_target_and_empty_packets() -> None:
    assert resolve_damage(pc(hp=0, dead=True), [pkt(5)]) == []
    with pytest.raises(ValueError):
        resolve_damage(pc(), [])


def test_golden_healing_capped_and_revives() -> None:
    # SRD 5.1 Healing: cannot exceed max HP; healing at 0 HP ends dying (and unconsciousness).
    assert resolve_healing(pc(hp=15), 10) == [HpChanged(creature_id="pc", delta=5, new_hp=20)]
    assert resolve_healing(pc(), 10) == []
    assert resolve_healing(pc(hp=0, dead=True), 10) == []
    down = pc(hp=6, death_save_failures=0)
    downed = run(down, resolve_damage(down, [pkt(8)]))
    downed = run(downed, [DeathSavesSet(creature_id="pc", successes=1, failures=2)])
    healed = run(downed, resolve_healing(downed, 4))
    assert (healed.hp, healed.conditions, healed.stable) == (4, [], False)
    assert (healed.death_save_successes, healed.death_save_failures) == (0, 0)
    with pytest.raises(ValueError):
        resolve_healing(pc(), -1)
