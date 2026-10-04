"""Hit points by level and temporary hit points.

Public API:
- `HIT_DIE_SIZES`: the class hit dice (d6, d8, d10, d12).
- `hp_gain_at_level_up(hit_die, con_mod) -> int`: the fixed average (die/2 + 1) + CON modifier,
  at least 1 (SRD 5.1 class tables "Hit Points at Higher Levels" fixed value; BG3 always uses it).
- `max_hp_at_level(hit_die, con_mod, level) -> int`: level 1 = hit die maximum + CON modifier
  (at least 1), plus `hp_gain_at_level_up` for each later level (SRD 5.1 "Hit Points at 1st
  Level"). The current CON modifier applies to every level (SRD: a CON change changes max HP).
- `gain_temp_hp(creature, amount) -> list[AnyEvent]`: SRD 5.1 "Temporary Hit Points": they do
  not stack; the creature keeps the higher of its current and the new amount. Returns one
  `TempHpSet` when the new amount is higher, otherwise no events.
"""

from aidm.models.events import AnyEvent, TempHpSet
from aidm.models.state import Creature
from aidm.rules.abilities import MAX_CLASS_LEVEL, MIN_LEVEL

HIT_DIE_SIZES: tuple[int, ...] = (6, 8, 10, 12)


def _check_die(hit_die: int) -> None:
    if hit_die not in HIT_DIE_SIZES:
        raise ValueError(f"hit die d{hit_die} is not a class hit die")


def hp_gain_at_level_up(hit_die: int, con_mod: int) -> int:
    _check_die(hit_die)
    return max(1, hit_die // 2 + 1 + con_mod)


def max_hp_at_level(hit_die: int, con_mod: int, level: int) -> int:
    _check_die(hit_die)
    if not MIN_LEVEL <= level <= MAX_CLASS_LEVEL:
        raise ValueError(f"level {level} outside {MIN_LEVEL}..{MAX_CLASS_LEVEL}")
    first = max(1, hit_die + con_mod)
    return first + (level - 1) * hp_gain_at_level_up(hit_die, con_mod)


def gain_temp_hp(creature: Creature, amount: int) -> list[AnyEvent]:
    if amount < 0:
        raise ValueError("temporary hit points must be >= 0")
    if amount <= creature.temp_hp:
        return []
    return [TempHpSet(creature_id=creature.id, temp_hp=amount)]
