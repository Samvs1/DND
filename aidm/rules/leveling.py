"""Experience and level-up 1 -> 5 (SPEC 7.2, 7.5): XP table, HP, proficiency, features, subclass,
ASI and spell learning, all as events. The data arrives as a `CharacterRegistries` argument.

Public API:
- `MAX_LEVEL` (5, the Tier-1 cap), `XP_THRESHOLDS` (SRD 5.1 "Character Advancement": 0, 300,
  900, 2700, 6500 for levels 1-5); `xp_for_level(level) -> int`, `level_for_xp(xp) -> int`
  (capped at MAX_LEVEL).
- `gain_xp(creature, amount) -> list[AnyEvent]`: `[XpGained]` (ValueError for a non-PC or a
  negative amount). Levels are taken with `level_up`, never automatically.
- `can_level_up(creature) -> bool`: a living PC under MAX_LEVEL with enough XP.
- `validate_level_up(creature, choices, regs) -> list[CreationError]`: every problem; [] = valid.
- `level_up(creature, choices, regs) -> list[AnyEvent]`: `LevelGained` (HP: fixed average + CON
  modifier per level with the new CON for every level, plus feature HP per level; current HP
  rises by the same amount; proficiency bonus; new class/subclass features and class/feature
  picks; ASI; spells), then the spell-slot (`slot_maximum_events`) and feature-resource
  (`feature_resource_events`) changes. `LevelUpInvalid(errors)` for choices that do not validate
  (nothing is produced, so nothing is consumed).
"""

from collections.abc import Mapping

from aidm.data.character_data import CharacterRegistries
from aidm.data.class_defs import ClassDef
from aidm.models.abilities import Ability, Skill
from aidm.models.character import PcData
from aidm.models.creation import CreationError, CreationErrorCode
from aidm.models.events import AnyEvent, LevelGained, XpGained
from aidm.models.leveling import LevelUpChoices
from aidm.models.state import Creature
from aidm.rules.abilities import ability_modifier, proficiency_bonus
from aidm.rules.creation_checks import pick_errors
from aidm.rules.feature_build import (
    expertise_picks,
    feature_choice_errors,
    feature_effects,
    feature_resource_events,
    with_picks,
)
from aidm.rules.hp import max_hp_at_level
from aidm.rules.level_spells import learned_spell_lists, spell_learning_errors
from aidm.rules.spellcasting import slot_maximum_events

MAX_LEVEL = 5
XP_THRESHOLDS: tuple[int, ...] = (0, 300, 900, 2700, 6500)
MAX_ABILITY_SCORE = 20
ASI_POINTS = 2
_E = CreationErrorCode


class LevelUpInvalid(ValueError):
    """`level_up` was handed choices that fail `validate_level_up` (callers validate first)."""

    def __init__(self, errors: list[CreationError]) -> None:
        super().__init__("; ".join(f"{e.field}: {e.code.value}" for e in errors))
        self.errors = errors


def _err(code: CreationErrorCode, field: str, detail: str) -> CreationError:
    return CreationError(code=code, field=field, detail=detail)


def xp_for_level(level: int) -> int:
    if not 1 <= level <= MAX_LEVEL:
        raise ValueError(f"level {level} outside 1..{MAX_LEVEL}")
    return XP_THRESHOLDS[level - 1]


def level_for_xp(xp: int) -> int:
    return max(i + 1 for i, threshold in enumerate(XP_THRESHOLDS) if xp >= threshold)


def gain_xp(creature: Creature, amount: int) -> list[AnyEvent]:
    if creature.pc is None:
        raise ValueError(f"{creature.id!r} is not a player character")
    if amount < 0:
        raise ValueError("experience gains are never negative")
    total = creature.pc.xp + amount
    return [XpGained(creature_id=creature.id, amount=amount, xp=total)]


def _gate_errors(creature: Creature) -> list[CreationError]:
    pc = creature.pc
    if pc is None:
        return [_err(_E.NOT_A_PC, "creature", f"{creature.id!r} is not a player character")]
    if creature.dead or creature.hp == 0:
        return [_err(_E.CANNOT_LEVEL_NOW, "creature", "a downed character cannot level up")]
    if pc.level >= MAX_LEVEL:
        return [_err(_E.MAX_LEVEL_REACHED, "level", f"level {MAX_LEVEL} is the cap")]
    needed = xp_for_level(pc.level + 1)
    if pc.xp < needed:
        return [_err(_E.NOT_ENOUGH_XP, "xp", f"{pc.xp} XP, level {pc.level + 1} needs {needed}")]
    return []


def can_level_up(creature: Creature) -> bool:
    return not _gate_errors(creature)


def _subclass(cls: ClassDef, level: int, choices: LevelUpChoices) -> list[CreationError]:
    if level == cls.subclass_level:
        if choices.subclass != cls.subclass_index:
            detail = f"choose a subclass: {cls.subclass_index!r}"
            return [_err(_E.SUBCLASS_INVALID, "subclass", detail)]
    elif choices.subclass is not None:
        detail = f"{cls.index} chooses its subclass at level {cls.subclass_level}"
        return [_err(_E.SUBCLASS_INVALID, "subclass", detail)]
    return []


def _new_features(
    pc: PcData, cls: ClassDef, level: int, choices: LevelUpChoices
) -> tuple[list[str], str | None]:
    subclass = cls.subclass_index if level == cls.subclass_level else pc.subclass
    gained = list(cls.level(level).features)
    if subclass is not None:
        gained += [f for row in cls.subclass_features if row.level == level for f in row.features]
    for choice in cls.choices:
        if choice.level == level:
            gained += choices.class_choices.get(choice.id, [])
    return list(dict.fromkeys(gained)), subclass


def _class_choice_errors(cls: ClassDef, level: int, choices: LevelUpChoices) -> list[CreationError]:
    due = {c.id: c for c in cls.choices if c.level == level}
    errors: list[CreationError] = []
    for choice_id, choice in due.items():
        picks = choices.class_choices.get(choice_id, [])
        field = f"class_choices.{choice_id}"
        errors += pick_errors(field, picks, count=choice.pick.choose, allowed=choice.pick.options)
    for choice_id in sorted(set(choices.class_choices) - set(due)):
        detail = f"no class choice {choice_id!r} at level {level}"
        errors.append(_err(_E.PICK_NOT_ALLOWED, f"class_choices.{choice_id}", detail))
    return errors


def _asi_errors(
    abilities: Mapping[Ability, int], asi: Mapping[Ability, int], due: bool
) -> list[CreationError]:
    if not due:
        return [_err(_E.ASI_INVALID, "asi", "no ability score improvement now")] if asi else []
    if sorted(asi.values()) not in ([ASI_POINTS], [1] * ASI_POINTS):
        return [_err(_E.ASI_INVALID, "asi", "+2 to one ability or +1 to two abilities")]
    over = sorted(a.value for a, v in asi.items() if abilities[a] + v > MAX_ABILITY_SCORE)
    if over:
        return [_err(_E.ASI_INVALID, "asi", f"{over} would exceed {MAX_ABILITY_SCORE}")]
    return []


def _raised(abilities: Mapping[Ability, int], asi: Mapping[Ability, int]) -> dict[Ability, int]:
    return {a: score + asi.get(a, 0) for a, score in abilities.items()}


def validate_level_up(
    creature: Creature, choices: LevelUpChoices, regs: CharacterRegistries
) -> list[CreationError]:
    errors = _gate_errors(creature)
    pc = creature.pc
    if errors or pc is None:
        return errors
    cls, level = regs.classes.get(pc.class_index), pc.level + 1
    errors += _subclass(cls, level, choices)
    errors += _class_choice_errors(cls, level, choices)
    gained, subclass = _new_features(pc, cls, level, choices)
    known = [f for f in gained if f in regs.features]
    proficient = [s.value for s in creature.skill_proficiencies]
    expert = [s.value for s in creature.skill_expertise]
    errors += feature_choice_errors(
        known, choices.feature_choices, regs.features, proficient, expert=expert
    )
    errors += _asi_errors(creature.abilities, choices.asi, cls.level(level).asi)
    abilities = _raised(creature.abilities, choices.asi)
    ids = [*pc.features, *known, *pc.traits]
    errors += spell_learning_errors(pc, cls, level, abilities, choices, regs, ids, subclass)
    return errors


def _new_pc(
    pc: PcData, cls: ClassDef, choices: LevelUpChoices, regs: CharacterRegistries
) -> PcData:
    level = pc.level + 1
    gained, subclass = _new_features(pc, cls, level, choices)
    features = with_picks([*pc.features, *gained], choices.feature_choices, regs.features)
    effects = feature_effects([*features, *pc.traits], level, regs.features)
    spells = learned_spell_lists(pc, cls, choices)
    return pc.model_copy(
        update={
            "level": level,
            "subclass": subclass,
            "features": features,
            "class_choices": {**pc.class_choices, **choices.class_choices},
            "feature_choices": {**pc.feature_choices, **choices.feature_choices},
            "armor_proficiencies": list(dict.fromkeys([*pc.armor_proficiencies, *effects.armor])),
            "weapon_proficiencies": list(
                dict.fromkeys([*pc.weapon_proficiencies, *effects.weapons])
            ),
            "tool_proficiencies": list(dict.fromkeys([*pc.tool_proficiencies, *effects.tools])),
            "cantrips": spells.cantrips,
            "spells_known": spells.spells_known,
            "spellbook": spells.spellbook,
            "prepared": spells.prepared,
        }
    )


def level_up(
    creature: Creature, choices: LevelUpChoices, regs: CharacterRegistries
) -> list[AnyEvent]:
    errors = validate_level_up(creature, choices, regs)
    if errors or creature.pc is None:
        raise LevelUpInvalid(errors)
    old = creature.pc
    cls = regs.classes.get(old.class_index)
    pc = _new_pc(old, cls, choices, regs)
    ids = [*pc.features, *pc.traits]
    before = feature_effects([*old.features, *old.traits], old.level, regs.features)
    effects = feature_effects(ids, pc.level, regs.features)
    abilities = _raised(creature.abilities, choices.asi)
    con_mod = ability_modifier(abilities[Ability.CON])
    max_hp = max_hp_at_level(cls.hit_die, con_mod, pc.level) + effects.hp_per_level * pc.level
    hp = min(max_hp, max(0, creature.hp + max_hp - creature.max_hp))
    new_expertise = expertise_picks(
        [f for f in pc.features if f not in old.features], choices.feature_choices, regs.features
    )
    skills = [*creature.skill_proficiencies, *(Skill(s) for s in effects.skills)]
    gained = LevelGained(
        creature_id=creature.id,
        max_hp=max_hp,
        hp=hp,
        proficiency_bonus=proficiency_bonus(pc.level),
        abilities=abilities,
        skill_proficiencies=list(dict.fromkeys(skills)),
        skill_expertise=list(dict.fromkeys([*creature.skill_expertise, *new_expertise])),
        resistances=list(dict.fromkeys([*creature.resistances, *effects.resistances])),
        speed=creature.speed + effects.speed - before.speed,
        darkvision=max(creature.darkvision, effects.darkvision),
        pc=pc,
    )
    resources = slot_maximum_events(creature, cls, pc.level)
    return [gained, *resources, *feature_resource_events(creature, ids, pc.level, regs.features)]
