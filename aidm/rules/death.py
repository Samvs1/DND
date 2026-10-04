"""Death saving throws and stabilising (SRD 5.1 "Dropping to 0 Hit Points").

Public API:
- `DEATH_SAVE_DC` (10), `STABILIZE_DC` (10, Wisdom (Medicine) check).
- `is_dying(creature) -> bool`: at 0 HP, alive, not stable, and makes death saves.
- `roll_death_save(rng, creature, *, adv=NORMAL, bonus=0) -> list[AnyEvent]`: d20 + `bonus`
  (Bless and the like) against DC 10. Natural 20: regain 1 HP (counters reset, the 0-HP
  unconscious condition is removed). Natural 1: two failures. Otherwise >= 10 one success,
  < 10 one failure. Three successes: `Stabilized`. Three failures: `CreatureDied`.
  Always starts with `DeathSaveRolled` carrying the d20 and the new counters.
  ValueError if the creature is not dying (callers only roll for dying creatures).
- `stabilize(creature) -> list[AnyEvent]`: an effect that stabilises (Spare the Dying, a healer's
  kit): `[Stabilized]` for a dying creature, else no events.
- `medicine_stabilize(rng, healer, target, *, adv=NORMAL, bonus=0) -> list[AnyEvent]`: the
  healer's Wisdom (Medicine) check against DC 10, logged as `CheckResolved`; on a success the
  target is stabilised. A target that is not dying yields no events and no roll.
"""

from aidm.models.abilities import Skill
from aidm.models.dice import AdvState
from aidm.models.events import (
    AnyEvent,
    CheckResolved,
    ConditionRemoved,
    CreatureDied,
    DeathSaveRolled,
    HpChanged,
    Stabilized,
)
from aidm.models.state import Creature
from aidm.rules.checks import skill_check
from aidm.rules.d20 import roll_d20
from aidm.rules.damage import MAX_DEATH_SAVES, UNCONSCIOUS, ZERO_HP_SOURCE, uses_death_saves
from aidm.rules.dice import Rng

DEATH_SAVE_DC = 10
STABILIZE_DC = 10


def is_dying(creature: Creature) -> bool:
    c = creature
    return c.hp == 0 and not c.dead and not c.stable and uses_death_saves(c)


def _nat20(creature: Creature) -> list[AnyEvent]:
    cid = creature.id
    return [
        HpChanged(creature_id=cid, delta=1, new_hp=1),
        ConditionRemoved(creature_id=cid, name=UNCONSCIOUS, source_id=ZERO_HP_SOURCE),
    ]


def roll_death_save(
    rng: Rng, creature: Creature, *, adv: AdvState = AdvState.NORMAL, bonus: int = 0
) -> list[AnyEvent]:
    if not is_dying(creature):
        raise ValueError(f"{creature.id!r} is not dying")
    d20 = roll_d20(rng, adv, bonus)
    successes = creature.death_save_successes
    failures = creature.death_save_failures
    if d20.natural == 20:
        successes, failures = 0, 0
    elif d20.natural == 1:
        failures = min(MAX_DEATH_SAVES, failures + 2)
    elif d20.total >= DEATH_SAVE_DC:
        successes = min(MAX_DEATH_SAVES, successes + 1)
    else:
        failures = min(MAX_DEATH_SAVES, failures + 1)
    cid = creature.id
    events: list[AnyEvent] = [
        DeathSaveRolled(creature_id=cid, roll=d20, successes=successes, failures=failures)
    ]
    if d20.natural == 20:
        events.extend(_nat20(creature))
    elif failures >= MAX_DEATH_SAVES:
        events.append(CreatureDied(creature_id=cid))
    elif successes >= MAX_DEATH_SAVES:
        events.append(Stabilized(creature_id=cid))
    return events


def stabilize(creature: Creature) -> list[AnyEvent]:
    if not is_dying(creature):
        return []
    return [Stabilized(creature_id=creature.id)]


def medicine_stabilize(
    rng: Rng,
    healer: Creature,
    target: Creature,
    *,
    adv: AdvState = AdvState.NORMAL,
    bonus: int = 0,
) -> list[AnyEvent]:
    if not is_dying(target):
        return []
    result = skill_check(rng, healer, Skill.MEDICINE, STABILIZE_DC, adv=adv, bonus=bonus)
    events: list[AnyEvent] = [
        CheckResolved(creature_id=healer.id, result=result, reason=f"stabilize {target.id}")
    ]
    if result.success:
        events.append(Stabilized(creature_id=target.id))
    return events
