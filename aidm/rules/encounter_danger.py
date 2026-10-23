"""Area danger (M29.6b): a monster's area damage counts in the danger it is rated and shown at.

The XP budget (`aidm.rules.encounter_budget`) only sees a monster's SRD XP, so a green dragon
wyrmling (450 XP) was "trivial" for four level-4 heroes while its breath took 14 and 21 hit
points, and a young black dragon rated "medium" breathed 51 and 47 on heroes with 30-48 (p3
1363, 1714). The danger of one area blast is its average damage against the heroes' average
hit point maximum; `EncounterTables.area_damage_rating` maps that share to a difficulty
(data). Area damage is a stat-block action with a saving throw DC, damage dice and a limited
use (Recharge 5-6, per day): breath weapons and their kin; SRD numbers are never changed.

Public API:
- `area_damage(monster) -> float`: the average damage of its strongest such action (0: none).
- `area_rating(monster, hero_hp, tables) -> Difficulty | None`: the difficulty its blast alone
  reaches against heroes of `hero_hp` average maximum hit points (None: below every share).
- `harder(a, b) -> Difficulty | None`: the higher of two ratings (None is below easy).
- `too_dangerous(monster, hero_hp, cap, tables) -> bool`: its area rating is above `cap`.
"""

from collections.abc import Sequence

from aidm.data.encounter_tables import EncounterTables
from aidm.data.srd_monster_actions import ActionDamage
from aidm.data.srd_monsters import SrdMonster
from aidm.models.encounter import Difficulty
from aidm.rules.dice import dice_max, dice_min

_ORDER = list(Difficulty)


def _average(parts: Sequence[ActionDamage]) -> float:
    dice = [p.damage_dice for p in parts if p.damage_dice]
    return sum((dice_min(d) + dice_max(d)) / 2 for d in dice)


def area_damage(monster: SrdMonster) -> float:
    blasts = [0.0]
    for action in monster.actions:
        if action.usage is None:
            continue
        if action.dc is not None:
            blasts.append(_average(action.damage))
        blasts += [_average(b.damage) for b in action.breath_options if b.dc is not None]
    return max(blasts)


def area_rating(monster: SrdMonster, hero_hp: float, tables: EncounterTables) -> Difficulty | None:
    damage = area_damage(monster)
    if damage <= 0 or hero_hp <= 0:
        return None
    share = damage / hero_hp
    reached = [Difficulty(k) for k, v in tables.area_damage_rating.items() if share >= v]
    return max(reached, key=_ORDER.index) if reached else None


def harder(a: Difficulty | None, b: Difficulty | None) -> Difficulty | None:
    if a is None or b is None:
        return a or b
    return a if _ORDER.index(a) >= _ORDER.index(b) else b


def too_dangerous(
    monster: SrdMonster, hero_hp: float, cap: Difficulty, tables: EncounterTables
) -> bool:
    rated = area_rating(monster, hero_hp, tables)
    return rated is not None and _ORDER.index(rated) > _ORDER.index(cap)
