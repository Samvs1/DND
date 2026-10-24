"""Area danger (M29.6b): a monster's area damage counts in the danger it is rated and shown at.

The XP budget (`aidm.rules.encounter_budget`) only sees a monster's SRD XP, so a green dragon
wyrmling (450 XP) was "trivial" for four level-4 heroes while its breath took 14 and 21 hit
points, and a young black dragon rated "medium" breathed 51 and 47 on heroes with 30-48 (p3
1363, 1714). The danger of one area blast is its average damage against the heroes' average
hit point maximum; `EncounterTables.area_damage_rating` maps that share to a difficulty
(data). Area damage is a stat-block action with a saving throw DC, damage dice and a limited
use (Recharge 5-6, per day): breath weapons and their kin; SRD numbers are never changed.
M31.1f: given the spell registry (`spells`), an area damage spell the monster can cast counts the
same way: a shipped spell of its kit that targets an area (fireball and kin) and that a slot of
its level or higher, an innate use or at-will casting pays for, at its base dice (no upcast).

Public API:
- `area_damage(monster, spells=None) -> float`: the average damage of its strongest such action,
  or with `spells` also such spell (0: none).
- `spell_area_damage(monster, spells) -> float`: the strongest area damage spell alone.
- `area_rating(monster, hero_hp, tables, spells=None) -> Difficulty | None`: the difficulty its
  blast alone reaches against heroes of `hero_hp` average maximum hit points (None: below every
  share).
- `harder(a, b) -> Difficulty | None`: the higher of two ratings (None is below easy).
- `too_dangerous(monster, hero_hp, cap, tables, spells=None) -> bool`: its area rating is above
  `cap`.
"""

from collections.abc import Sequence

from aidm.data.encounter_tables import EncounterTables
from aidm.data.registry import Registry
from aidm.data.spell_defs import (
    AttackRollEffect,
    DamageEffect,
    Effect,
    MultiTargetEffect,
    SaveEffect,
    SpellDef,
)
from aidm.data.srd_monster_actions import ActionDamage, MonsterSpell, Spellcasting
from aidm.data.srd_monsters import SrdMonster
from aidm.models.encounter import Difficulty
from aidm.rules.dice import dice_max, dice_min
from aidm.rules.monster_keys import spell_index

_ORDER = list(Difficulty)


def _average(parts: Sequence[ActionDamage]) -> float:
    return sum(_dice_average(p.damage_dice) for p in parts if p.damage_dice)


def _dice_average(dice: str) -> float:
    return (dice_min(dice) + dice_max(dice)) / 2


def _effects_damage(effects: Sequence[Effect]) -> float:
    total = 0.0
    for effect in effects:
        if isinstance(effect, DamageEffect):
            total += _dice_average(effect.dice)
        elif isinstance(effect, SaveEffect):
            total += _effects_damage(effect.on_fail)
        elif isinstance(effect, AttackRollEffect):
            total += _effects_damage(effect.on_hit)
        elif isinstance(effect, MultiTargetEffect):
            total += _effects_damage(effect.effects)
    return total


def _castable(kit: Spellcasting, spell: MonsterSpell) -> bool:
    if spell.level == 0 or spell.usage is not None:
        return True
    return any(
        level.isdigit() and int(level) >= spell.level and count > 0
        for level, count in kit.slots.items()
    )


def spell_area_damage(monster: SrdMonster, spells: Registry[SpellDef]) -> float:
    blasts = [0.0]
    for ability in monster.special_abilities:
        kit = ability.spellcasting
        if kit is None:
            continue
        for spell in kit.spells:
            found = spells.find(spell_index(spell.url))
            if found is None or found.targeting.kind != "area" or not _castable(kit, spell):
                continue
            blasts.append(_effects_damage(found.effects))
    return max(blasts)


def area_damage(monster: SrdMonster, spells: Registry[SpellDef] | None = None) -> float:
    blasts = [0.0 if spells is None else spell_area_damage(monster, spells)]
    for action in monster.actions:
        if action.usage is None:
            continue
        if action.dc is not None:
            blasts.append(_average(action.damage))
        blasts += [_average(b.damage) for b in action.breath_options if b.dc is not None]
    return max(blasts)


def area_rating(
    monster: SrdMonster,
    hero_hp: float,
    tables: EncounterTables,
    spells: Registry[SpellDef] | None = None,
) -> Difficulty | None:
    damage = area_damage(monster, spells)
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
    monster: SrdMonster,
    hero_hp: float,
    cap: Difficulty,
    tables: EncounterTables,
    spells: Registry[SpellDef] | None = None,
) -> bool:
    rated = area_rating(monster, hero_hp, tables, spells)
    return rated is not None and _ORDER.index(rated) > _ORDER.index(cap)
