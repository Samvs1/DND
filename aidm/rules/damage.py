"""THE damage choke point, plus healing. Every damage path in the engine calls `resolve_damage`.

Public API:
- `UNCONSCIOUS`, `ZERO_HP_SOURCE`: a creature dropped to 0 HP gets the "unconscious" condition
  with `source_id="zero_hp"`; healing above 0 removes exactly that instance.
- `uses_death_saves(creature) -> bool`: `creature.death_saves`, or PC-only when it is None.
- `damage_after_defenses(creature, packet) -> int`: SRD 5.1 "Damage Resistance and
  Vulnerability" (the creature's own defences plus those its conditions grant, e.g. petrified):
  immunity -> 0; resistance halves (round down); vulnerability doubles; with both
  resistance and vulnerability, halve then double. Negative raw amounts clamp to 0 first.
- `resolve_damage(target, packets, *, crit=False, source_id=None) -> list[AnyEvent]`: one hit or
  source of damage (all its typed packets together). Emits, in order: `DamageTaken` (log, with
  per-packet results and the total for the M1.5 concentration hook), `TempHpSet` (temp HP absorb
  first; any damage first ends the conditions that end on damage, e.g. magical sleep),
  `HpChanged` (HP clamped to [0, max]), then the 0-HP consequences:
  - dropped to 0 from above: creatures without death saves die (`CreatureDied`); others die
    instantly if the damage left after reaching 0 is >= max HP (SRD "Instant Death"), else become
    unconscious and dying (`ConditionApplied` unconscious, counters reset if stale);
  - already at 0: damage >= max HP kills; otherwise one death save failure, two on a crit, and the
    creature is no longer stable (`DeathSavesSet`); a third failure adds `CreatureDied`
    (SRD "Damage at 0 Hit Points"). Damage fully absorbed by temp HP causes no failure.
  A dead target yields no events. At least one packet is required.
- `resolve_healing(target, amount) -> list[AnyEvent]`: SRD "Healing": HP rise by `amount`, never
  above max; nothing for the dead; healing from 0 removes the 0-HP unconscious condition and
  resets the death-save state (`DeathSavesSet`).
"""

from collections.abc import Sequence

from aidm.models.damage import DamagePacket, DamagePart
from aidm.models.events import (
    AnyEvent,
    ConditionApplied,
    ConditionRemoved,
    CreatureDied,
    DamageTaken,
    DeathSavesSet,
    HpChanged,
    TempHpSet,
)
from aidm.models.state import ActiveCondition, Creature, CreatureKind
from aidm.rules.conditions import condition_immune, condition_resists, damage_ended_conditions

UNCONSCIOUS = "unconscious"
ZERO_HP_SOURCE = "zero_hp"
MAX_DEATH_SAVES = 3


def uses_death_saves(creature: Creature) -> bool:
    if creature.death_saves is not None:
        return creature.death_saves
    return creature.kind is CreatureKind.PC


def damage_after_defenses(creature: Creature, packet: DamagePacket) -> int:
    amount = max(0, packet.amount)
    if packet.damage_type in creature.immunities or condition_immune(creature, packet.damage_type):
        return 0
    if packet.damage_type in creature.resistances or condition_resists(
        creature, packet.damage_type
    ):
        amount //= 2
    if packet.damage_type in creature.vulnerabilities:
        amount *= 2
    return amount


def _reset_death_state(creature: Creature) -> list[AnyEvent]:
    c = creature
    if c.death_save_successes or c.death_save_failures or c.stable:
        return [DeathSavesSet(creature_id=c.id)]
    return []


def _dropped_to_zero(target: Creature, overflow: int) -> list[AnyEvent]:
    if not uses_death_saves(target) or overflow >= target.max_hp:
        return [CreatureDied(creature_id=target.id)]
    condition = ActiveCondition(name=UNCONSCIOUS, source_id=ZERO_HP_SOURCE)
    return [
        ConditionApplied(creature_id=target.id, condition=condition),
        *_reset_death_state(target),
    ]


def _hit_at_zero(target: Creature, damage: int, crit: bool) -> list[AnyEvent]:
    if not uses_death_saves(target) or damage >= target.max_hp:
        return [CreatureDied(creature_id=target.id)]
    failures = min(MAX_DEATH_SAVES, target.death_save_failures + (2 if crit else 1))
    events: list[AnyEvent] = [
        DeathSavesSet(
            creature_id=target.id,
            successes=target.death_save_successes,
            failures=failures,
            stable=False,
        )
    ]
    if failures >= MAX_DEATH_SAVES:
        events.append(CreatureDied(creature_id=target.id))
    return events


def resolve_damage(
    target: Creature,
    packets: Sequence[DamagePacket],
    *,
    crit: bool = False,
    source_id: str | None = None,
) -> list[AnyEvent]:
    if not packets:
        raise ValueError("resolve_damage needs at least one damage packet")
    if target.dead:
        return []
    parts = tuple(
        DamagePart(
            damage_type=p.damage_type,
            rolled=max(0, p.amount),
            taken=damage_after_defenses(target, p),
        )
        for p in packets
    )
    total = sum(part.taken for part in parts)
    absorbed = min(target.temp_hp, total)
    remaining = total - absorbed
    hp_lost = min(target.hp, remaining)
    events: list[AnyEvent] = [
        DamageTaken(
            creature_id=target.id,
            parts=parts,
            total=total,
            temp_absorbed=absorbed,
            hp_lost=hp_lost,
            crit=crit,
            source_id=source_id,
        )
    ]
    if total > 0:
        events.extend(
            ConditionRemoved(
                creature_id=target.id, name=c.name, source_id=c.source_id, exact_source=True
            )
            for c in damage_ended_conditions(target)
        )
    if absorbed:
        events.append(TempHpSet(creature_id=target.id, temp_hp=target.temp_hp - absorbed))
    if hp_lost:
        new_hp = target.hp - hp_lost
        events.append(HpChanged(creature_id=target.id, delta=-hp_lost, new_hp=new_hp))
    if remaining and target.hp == 0:
        events.extend(_hit_at_zero(target, remaining, crit))
    elif remaining and target.hp == hp_lost:
        events.extend(_dropped_to_zero(target, remaining - hp_lost))
    return events


def resolve_healing(target: Creature, amount: int) -> list[AnyEvent]:
    if amount < 0:
        raise ValueError("healing amount must be >= 0")
    if target.dead:
        return []
    new_hp = min(target.max_hp, target.hp + amount)
    if new_hp == target.hp:
        return []
    events: list[AnyEvent] = [
        HpChanged(creature_id=target.id, delta=new_hp - target.hp, new_hp=new_hp)
    ]
    if target.hp == 0:
        events.append(
            ConditionRemoved(creature_id=target.id, name=UNCONSCIOUS, source_id=ZERO_HP_SOURCE)
        )
        events.extend(_reset_death_state(target))
    return events
