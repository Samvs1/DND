"""Creation-rule checks and re-derivations for character import (QA-04, DECISIONS M9.5).

`aidm.rules.character_io` refuses unknown references and re-derives the combat numbers; this
module adds the creation rules a hand-edited file could break:
- base scores: all six, each 3..18, total at most `MAX_BASE_TOTAL` (point buy and the standard
  array always fit; a 4d6 set cannot be re-verified because the issued rolls are not stored);
- final scores per ability: base + that ability's largest possible racial bonus + every ASI point;
- skills: background and race grants plus feature skills, and at most the class and race pick
  counts from their option lists;
- re-derived (tampering only ever adds, so they are filtered or reset): expertise only from
  expertise features' stored picks, armor and weapon proficiencies only from class, race and
  features, size from the race, no condition immunities (no shipped race or feature grants one),
  no temporary HP, and gold capped at the background's starting gold + `GOLD_PER_LEVEL` per level
  above the first.

Public API: `MAX_BASE_TOTAL`, `GOLD_PER_LEVEL`, `build_errors(creature, cls, race, sub, regs)`,
`rederive_picks(creature, cls, race, sub, regs) -> Creature`.
"""

from aidm.data.character_data import CharacterRegistries
from aidm.data.class_defs import ClassDef
from aidm.data.race_defs import RaceDef, SubraceDef
from aidm.models.abilities import Ability, Skill
from aidm.models.character import PcData, Size
from aidm.models.creation import CreationError, CreationErrorCode
from aidm.models.state import Creature
from aidm.rules.feature_build import expertise_counts, feature_effects

MIN_BASE, MAX_BASE, MAX_BASE_TOTAL = 3, 18, 80
GOLD_PER_LEVEL = 200
ASI_POINTS = 2
_E = CreationErrorCode


def _err(code: CreationErrorCode, field: str, detail: str) -> CreationError:
    return CreationError(code=code, field=field, detail=detail)


def _base_errors(pc: PcData) -> list[CreationError]:
    base = pc.base_abilities
    missing = [a.value for a in Ability if a not in base]
    if missing:
        return [_err(_E.ABILITY_MISSING, "pc.base_abilities", f"missing {missing}")]
    errors = [
        _err(_E.SCORE_OUT_OF_RANGE, f"pc.base_abilities.{a.value}", f"{s} outside 3..18")
        for a, s in base.items()
        if not MIN_BASE <= s <= MAX_BASE
    ]
    if sum(base.values()) > MAX_BASE_TOTAL:
        detail = f"base total {sum(base.values())} above {MAX_BASE_TOTAL}"
        errors.append(_err(_E.SCORE_OUT_OF_RANGE, "pc.base_abilities", detail))
    return errors


def _racial_max(race: RaceDef, sub: SubraceDef | None) -> dict[Ability, int]:
    bonus = dict.fromkeys(Ability, 0)
    for entry in [*race.ability_bonuses, *(sub.ability_bonuses if sub else ())]:
        bonus[Ability(entry.ability)] += entry.bonus
    if race.ability_choice is not None:
        for option in race.ability_choice.options:
            bonus[Ability(option)] += race.ability_choice_bonus
    return bonus


def _score_errors(
    creature: Creature, cls: ClassDef, race: RaceDef, sub: SubraceDef | None
) -> list[CreationError]:
    pc = creature.pc
    assert pc is not None
    asi = sum(1 for lv in range(1, pc.level + 1) if cls.level(lv).asi) * ASI_POINTS
    racial = _racial_max(race, sub)
    return [
        _err(_E.SCORE_OUT_OF_RANGE, f"abilities.{a.value}", f"{score} above what the build allows")
        for a, score in creature.abilities.items()
        if a in pc.base_abilities and score > pc.base_abilities[a] + racial[a] + asi
    ]


def _granted_skills(
    pc: PcData, race: RaceDef, sub: SubraceDef | None, regs: CharacterRegistries
) -> set[str]:
    background = regs.backgrounds.get(pc.background)
    effects = feature_effects([*pc.features, *pc.traits], pc.level, regs.features)
    sub_skills = sub.skills if sub else ()
    return {*background.skills, *race.skills, *sub_skills, *effects.skills}


def _skill_errors(
    creature: Creature,
    cls: ClassDef,
    race: RaceDef,
    sub: SubraceDef | None,
    regs: CharacterRegistries,
) -> list[CreationError]:
    pc = creature.pc
    assert pc is not None
    picked = [s.value for s in creature.skill_proficiencies]
    picked = [s for s in dict.fromkeys(picked) if s not in _granted_skills(pc, race, sub, regs)]
    options = {*cls.skill_choice.options, *(race.skill_choice.options if race.skill_choice else ())}
    count = cls.skill_choice.choose + (race.skill_choice.choose if race.skill_choice else 0)
    errors = [
        _err(_E.PICK_NOT_ALLOWED, "skill_proficiencies", f"{s!r} is not a pick for this hero")
        for s in picked
        if s not in options
    ]
    if len(picked) > count:
        detail = f"{len(picked)} picked skills, at most {count}"
        errors.append(_err(_E.PICK_COUNT, "skill_proficiencies", detail))
    return errors


def build_errors(
    creature: Creature,
    cls: ClassDef,
    race: RaceDef,
    sub: SubraceDef | None,
    regs: CharacterRegistries,
) -> list[CreationError]:
    pc = creature.pc
    assert pc is not None
    errors = _base_errors(pc)
    if not errors:
        errors += _score_errors(creature, cls, race, sub)
    return errors + _skill_errors(creature, cls, race, sub, regs)


def _expertise(creature: Creature, pc: PcData, regs: CharacterRegistries) -> list[Skill]:
    proficient = set(creature.skill_proficiencies)
    allowed: set[Skill] = set()
    for feature_id, count in expertise_counts([*pc.features, *pc.traits], regs.features).items():
        picks = [Skill(s) for s in pc.feature_choices.get(feature_id, []) if s in Skill]
        allowed.update(s for s in picks[:count] if s in proficient)
    return [s for s in dict.fromkeys(creature.skill_expertise) if s in allowed]


def rederive_picks(
    creature: Creature,
    cls: ClassDef,
    race: RaceDef,
    sub: SubraceDef | None,
    regs: CharacterRegistries,
) -> Creature:
    pc = creature.pc
    assert pc is not None
    effects = feature_effects([*pc.features, *pc.traits], pc.level, regs.features)
    armor = {*cls.armor, *effects.armor}
    race_weapons = [*race.weapon_proficiencies, *(sub.weapon_proficiencies if sub else ())]
    weapons = {*cls.weapons, *race_weapons, *effects.weapons}
    gold_cap = regs.backgrounds.get(pc.background).gold + GOLD_PER_LEVEL * (pc.level - 1)
    new_pc = pc.model_copy(
        update={
            "armor_proficiencies": [a for a in pc.armor_proficiencies if a in armor],
            "weapon_proficiencies": [w for w in pc.weapon_proficiencies if w in weapons],
            "gold": min(pc.gold, gold_cap),
        }
    )
    return creature.model_copy(
        update={
            "skill_expertise": _expertise(creature, pc, regs),
            "condition_immunities": [],
            "size": Size(race.size),
            "temp_hp": 0,
            "pc": new_pc,
        }
    )
