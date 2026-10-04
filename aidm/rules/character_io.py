"""Character JSON export and import (SPEC 8: "A character can be exported/imported as JSON").

Pure functions: the text goes in or out as an argument, never a file. Import never trusts the
file: it re-validates the model, refuses unknown references and impossible progress, then
RE-DERIVES every stat the rules own (docs/DECISIONS.md M2.6).

Public API:
- `export_character(creature) -> str`: JSON document `{"format": "aidm.character", "version": 1,
  "character": <Creature>}` (ValueError for a creature that is not a PC).
- `import_character(text, regs) -> Creature`: the validated character with proficiency bonus,
  saving throws, max HP, AC, speed, darkvision, resistances, immunities and resource maxima
  recomputed from class, race and features (current HP and resource counts are kept, clamped to
  the new maxima). Anything else is refused.
- `CharacterImportInvalid(errors)`: the typed refusal; `errors` are `CreationError`s (unknown
  race/subrace/class/background/subclass/feature/spell/item, score out of range, level and XP
  that disagree, or IMPORT_INVALID for malformed JSON).
"""

import json
from collections.abc import Container, Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from aidm.data.character_data import CharacterRegistries
from aidm.data.class_defs import ClassDef
from aidm.data.race_defs import RaceDef, SubraceDef
from aidm.models.abilities import Ability
from aidm.models.creation import CreationError, CreationErrorCode
from aidm.models.state import Creature, CreatureKind, Resource
from aidm.rules.abilities import ability_modifier, proficiency_bonus
from aidm.rules.defense import armor_class
from aidm.rules.feature_build import feature_effects, feature_resources
from aidm.rules.features import feature_ac_bonus
from aidm.rules.hp import max_hp_at_level
from aidm.rules.leveling import MAX_LEVEL, xp_for_level
from aidm.rules.spellcasting import slot_resources

FORMAT = "aidm.character"
VERSION = 1
MIN_SCORE, MAX_SCORE, ASI_POINTS = 1, 20, 2
_E = CreationErrorCode


class CharacterImportInvalid(ValueError):
    def __init__(self, errors: list[CreationError]) -> None:
        super().__init__("; ".join(f"{e.field}: {e.detail}" for e in errors))
        self.errors = errors


class _Document(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["aidm.character"]
    version: Literal[1]
    character: Creature


def _err(code: CreationErrorCode, field: str, detail: str) -> CreationError:
    return CreationError(code=code, field=field, detail=detail)


def export_character(creature: Creature) -> str:
    if creature.kind is not CreatureKind.PC or creature.pc is None:
        raise ValueError("only a player character can be exported")
    document = _Document(format=FORMAT, version=VERSION, character=creature)
    return json.dumps(document.model_dump(mode="json"), indent=2, ensure_ascii=False)


def _parse(text: str) -> Creature:
    try:
        document = _Document.model_validate_json(text)
    except ValidationError as exc:
        errors = [
            _err(_E.IMPORT_INVALID, ".".join(str(p) for p in e["loc"]) or "json", e["msg"])
            for e in exc.errors()
        ]
        raise CharacterImportInvalid(errors) from exc
    if document.character.kind is not CreatureKind.PC or document.character.pc is None:
        raise CharacterImportInvalid([_err(_E.NOT_A_PC, "kind", "not a player character")])
    return document.character


def _unknown(field: str, ids: Iterable[str], known: Container[str]) -> list[CreationError]:
    return [_err(_E.PICK_NOT_ALLOWED, field, f"unknown {i!r}") for i in ids if i not in known]


def _refs(
    creature: Creature, regs: CharacterRegistries
) -> tuple[ClassDef, RaceDef, SubraceDef | None]:
    pc = creature.pc
    assert pc is not None
    errors: list[CreationError] = []
    race, cls = regs.races.find(pc.race), regs.classes.find(pc.class_index)
    if race is None:
        errors.append(_err(_E.UNKNOWN_RACE, "race", f"unknown race {pc.race!r}"))
    if cls is None:
        errors.append(_err(_E.UNKNOWN_CLASS, "class_index", f"unknown class {pc.class_index!r}"))
    if pc.background not in regs.backgrounds:
        errors.append(_err(_E.UNKNOWN_BACKGROUND, "background", f"unknown {pc.background!r}"))
    sub = next((s for s in race.subraces if s.index == pc.subrace), None) if race else None
    if race and (bool(pc.subrace) != bool(race.subraces) or (pc.subrace and sub is None)):
        errors.append(_err(_E.UNKNOWN_SUBRACE, "subrace", f"subrace {pc.subrace!r} does not fit"))
    if errors or race is None or cls is None:
        raise CharacterImportInvalid(errors)
    return cls, race, sub


def _content_errors(
    creature: Creature, cls: ClassDef, regs: CharacterRegistries
) -> list[CreationError]:
    pc = creature.pc
    assert pc is not None
    spells = [*pc.cantrips, *pc.race_cantrips, *pc.spells_known, *pc.spellbook, *pc.prepared]
    gear = [i.item for i in pc.inventory if not i.item.startswith("scroll-of-")]
    worn = [i for i in pc.equipped.model_dump().values() if i]
    errors = _unknown("features", [*pc.features, *pc.traits], regs.features)
    errors += _unknown("spells", spells, regs.spells)
    errors += _unknown("inventory", [*gear, *worn], regs.equipment)
    if pc.subclass is not None and (
        pc.subclass != cls.subclass_index or pc.level < cls.subclass_level
    ):
        errors.append(_err(_E.SUBCLASS_INVALID, "subclass", f"{pc.subclass!r} not available"))
    return errors


def _progress_errors(
    creature: Creature, cls: ClassDef, race: RaceDef, sub: SubraceDef | None
) -> list[CreationError]:
    pc = creature.pc
    assert pc is not None
    errors: list[CreationError] = []
    if not 1 <= pc.level <= MAX_LEVEL or pc.xp < xp_for_level(pc.level):
        errors.append(_err(_E.NOT_ENOUGH_XP, "level", f"level {pc.level} with {pc.xp} xp"))
        if not 1 <= pc.level <= MAX_LEVEL:
            return errors
    for ability, score in creature.abilities.items():
        if not MIN_SCORE <= score <= MAX_SCORE:
            detail = f"{ability.value} {score} outside {MIN_SCORE}..{MAX_SCORE}"
            errors.append(_err(_E.SCORE_OUT_OF_RANGE, f"abilities.{ability.value}", detail))
    fixed = [*race.ability_bonuses, *(sub.ability_bonuses if sub else ())]
    picks = race.ability_choice.choose if race.ability_choice else 0
    racial = sum(b.bonus for b in fixed) + picks * race.ability_choice_bonus
    asi = sum(1 for lv in range(1, pc.level + 1) if cls.level(lv).asi) * ASI_POINTS
    if sum(creature.abilities.values()) > sum(pc.base_abilities.values()) + racial + asi:
        errors.append(_err(_E.SCORE_OUT_OF_RANGE, "abilities", "more points than the build allows"))
    return errors


def _resources(creature: Creature, cls: ClassDef, regs: CharacterRegistries) -> dict[str, Resource]:
    pc = creature.pc
    assert pc is not None
    ids = [*pc.features, *pc.traits]
    fresh = {**slot_resources(cls, pc.level), **feature_resources(ids, pc.level, regs.features)}
    kept: dict[str, Resource] = {}
    for key, resource in fresh.items():
        old = creature.resources.get(key)
        current = min(old.current, resource.maximum) if old else resource.current
        kept[key] = resource.model_copy(update={"current": current})
    return kept


def _derive(
    creature: Creature, cls: ClassDef, race: RaceDef, regs: CharacterRegistries
) -> Creature:
    pc = creature.pc
    assert pc is not None
    effects = feature_effects([*pc.features, *pc.traits], pc.level, regs.features)
    con_mod = ability_modifier(creature.abilities[Ability.CON])
    max_hp = max_hp_at_level(cls.hit_die, con_mod, pc.level) + effects.hp_per_level * pc.level
    armor = regs.equipment.get(pc.equipped.armor) if pc.equipped.armor else None
    shield = regs.equipment.get(pc.equipped.shield) if pc.equipped.shield else None
    derived = creature.model_copy(
        update={
            "proficiency_bonus": proficiency_bonus(pc.level),
            "save_proficiencies": [Ability(a) for a in cls.saving_throws],
            "max_hp": max_hp,
            "hp": min(creature.hp, max_hp),
            "ac": armor_class(creature.abilities, armor=armor, shield=shield),
            "speed": race.speed + effects.speed,
            "darkvision": max(race.darkvision, effects.darkvision),
            "resistances": list(effects.resistances),
            "immunities": [],
            "vulnerabilities": [],
            "resources": _resources(creature, cls, regs),
        }
    )
    bonus = feature_ac_bonus(derived, regs.features, armored=pc.equipped.armor is not None)
    return derived.model_copy(update={"ac": derived.ac + bonus})


def import_character(text: str, regs: CharacterRegistries) -> Creature:
    creature = _parse(text)
    cls, race, sub = _refs(creature, regs)
    errors = _content_errors(creature, cls, regs) + _progress_errors(creature, cls, race, sub)
    if errors:
        raise CharacterImportInvalid(errors)
    return _derive(creature, cls, race, regs)
