"""SRD stat block -> `Creature` (the combat instance of a monster).

`creature_from_monster(monster, creature_id, *, name=None) -> Creature`, with kind MONSTER:
- HP: the stat block's fixed average `hit_points` (no rolled HP: predictable budgets, and the
  host difficulty multiplier is a later layer).
- AC: the primary armor class value. Abilities: the six scores. Proficiency bonus: SRD value.
- Saves: every `saving-throw-<ability>` proficiency. Skills: every `skill-<name>` proficiency;
  a listed bonus of at least ability modifier + 2 x proficiency bonus counts as expertise
  (the goblin's Stealth +6). Listed bonuses are otherwise re-derived, not stored.
- Damage defences: each SRD string contributes the damage types named in it. Strings that only
  apply "from nonmagical" attacks count fully (party weapons at levels 1-5 are mundane); any
  other qualified string ("damage from spells", "from magic weapons wielded by good creatures")
  is ignored. Condition immunities: the SRD condition indexes (they equal our condition keys).
- Speed: the walking speed, or the best other speed (fly, swim, climb, burrow) when the stat block
  has no walking speed. Size and darkvision from the stat block. Monsters die at 0 HP
  (`death_saves` None).
The stat block is an ARGUMENT; rules never load data.
"""

import re

from aidm.data.srd_monsters import SrdMonster
from aidm.models.abilities import ABILITIES, SKILL_ABILITY, Ability, Skill
from aidm.models.character import Size
from aidm.models.damage import DamageType
from aidm.models.state import Creature, CreatureKind
from aidm.rules.abilities import ability_modifier

_FEET = re.compile(r"(\d+)\s*ft")
_SAVE_PREFIX = "saving-throw-"
_SKILL_PREFIX = "skill-"
_NONMAGICAL = "nonmagical"


def _feet(text: str | None) -> int:
    if not text:
        return 0
    match = _FEET.search(text)
    return int(match.group(1)) if match else 0


def _damage_types(entries: list[str]) -> list[DamageType]:
    found: list[DamageType] = []
    for text in entries:
        lowered = text.lower()
        if " from " in lowered and _NONMAGICAL not in lowered:
            continue
        for damage_type in DamageType:
            if re.search(rf"\b{damage_type.value}\b", lowered) and damage_type not in found:
                found.append(damage_type)
    return found


def _speed(monster: SrdMonster) -> int:
    walk = _feet(monster.speed.walk)
    if walk:
        return walk
    s = monster.speed
    return max(_feet(s.fly), _feet(s.swim), _feet(s.climb), _feet(s.burrow))


def _proficiencies(
    monster: SrdMonster, abilities: dict[Ability, int]
) -> tuple[list[Ability], list[Skill], list[Skill]]:
    saves: list[Ability] = []
    skills: list[Skill] = []
    expertise: list[Skill] = []
    pb = monster.proficiency_bonus
    for prof in monster.proficiencies:
        index = prof.proficiency.index
        if index.startswith(_SAVE_PREFIX):
            saves.append(Ability(index.removeprefix(_SAVE_PREFIX)))
        elif index.startswith(_SKILL_PREFIX):
            skill = Skill(index.removeprefix(_SKILL_PREFIX))
            skills.append(skill)
            if prof.value >= ability_modifier(abilities[SKILL_ABILITY[skill]]) + 2 * pb:
                expertise.append(skill)
    return saves, skills, expertise


def creature_from_monster(
    monster: SrdMonster, creature_id: str, *, name: str | None = None
) -> Creature:
    abilities = {a: monster.ability_score(a.value) for a in ABILITIES}
    saves, skills, expertise = _proficiencies(monster, abilities)
    return Creature(
        id=creature_id,
        name=name or monster.name,
        kind=CreatureKind.MONSTER,
        abilities=abilities,
        max_hp=monster.hit_points,
        hp=monster.hit_points,
        ac=monster.ac,
        proficiency_bonus=monster.proficiency_bonus,
        save_proficiencies=saves,
        skill_proficiencies=skills,
        skill_expertise=expertise,
        resistances=_damage_types(monster.damage_resistances),
        immunities=_damage_types(monster.damage_immunities),
        vulnerabilities=_damage_types(monster.damage_vulnerabilities),
        condition_immunities=[c.index for c in monster.condition_immunities],
        speed=_speed(monster),
        size=Size(monster.size),
        darkvision=_feet(monster.senses.darkvision),
    )
