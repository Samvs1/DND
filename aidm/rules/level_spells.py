"""BG3-style spell learning on level-up (SPEC 7.2): validation and the resulting spell lists.

Counts come from the class level rows (`aidm.rules.spellcasting`), capped by the shipped
spells still open (`creation_checks.pick_count`); lists from the SRD class spell lists plus
feature `expanded` grants (warlock patron), shipped spells only. Rules per caster kind:
- every caster: new cantrips = `cantrips_known(new) - cantrips_known(old)`, from the class list.
- known and pact casters: new spells = `spells_known(new) - spells_known(old)` of a level they
  have slots for; they may also swap ONE known spell (`replace_spell` -> `replacement`).
- spellbook casters (wizard): `spellbook_per_level` spells added to the book (slot levels only).
- prepared casters: an optional `prepared` list from the book (wizard) or the class list
  (cleric), at most `prepared_spell_limit` with the new scores. M29.9a T20: a level-up never
  re-picks: the spells already prepared stay, the picked ones are added, and a wizard's free
  room is filled with the spells just written into the book, then the rest of the book in
  book order, up to the new limit (SRD 5.1: Int modifier + wizard level, at least 1).
Before the class's `first_level` (ranger 1) nothing may be picked.

Public API:
- `learnable_spells(class_def, level, feature_ids, subclass, regs) -> set[str]`: levelled spells
  this class may learn at this level (class list plus expanded grants, slot levels only).
- `spell_learning_errors(pc, class_def, level, abilities, choices, regs, feature_ids, subclass)
  -> list[CreationError]` for the level being gained (`feature_ids` and `subclass` as they
  will be after it).
- `learned_spell_lists(pc, class_def, choices, prepared_limit) -> LearnedSpells`: the new
  `cantrips`, `spells_known`, `spellbook`, `prepared` lists (valid choices only).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from aidm.data.character_data import CharacterRegistries
from aidm.data.class_defs import ClassDef
from aidm.models.abilities import Ability
from aidm.models.character import PcData
from aidm.models.creation import CreationError, CreationErrorCode
from aidm.models.leveling import LevelUpChoices
from aidm.rules.creation_checks import class_spell_indexes, pick_count, pick_errors
from aidm.rules.feature_build import expanded_spell_indexes
from aidm.rules.spellcasting import (
    cantrips_known_count,
    max_spell_level,
    prepared_spell_limit,
    spells_known_count,
)

_E = CreationErrorCode


@dataclass(frozen=True)
class LearnedSpells:
    cantrips: list[str]
    spells_known: list[str]
    spellbook: list[str]
    prepared: list[str]


def _err(code: CreationErrorCode, field: str, detail: str) -> CreationError:
    return CreationError(code=code, field=field, detail=detail)


def learnable_spells(
    class_def: ClassDef,
    level: int,
    feature_ids: Sequence[str],
    subclass: str | None,
    regs: CharacterRegistries,
) -> set[str]:
    top = max_spell_level(class_def, level)
    pool = class_spell_indexes(regs.spells, class_def.index, 1, top)
    expanded = expanded_spell_indexes(feature_ids, level, subclass, regs.features)
    return pool | {s for s in expanded if (spell := regs.spells.find(s)) and spell.level <= top}


def _no_picks_errors(choices: LevelUpChoices) -> list[CreationError]:
    errors: list[CreationError] = []
    for field, picked in (("cantrips", choices.cantrips), ("spells", choices.spells)):
        if picked:
            errors.append(_err(_E.PICK_COUNT, field, "this level learns no spells"))
    if choices.prepared is not None:
        errors.append(_err(_E.PICK_NOT_ALLOWED, "prepared", "nothing to prepare at this level"))
    if choices.replace_spell or choices.replacement:
        errors.append(_err(_E.REPLACEMENT_INVALID, "replace_spell", "no spell to replace"))
    return errors


def _replacement_errors(pc: PcData, choices: LevelUpChoices, pool: set[str]) -> list[CreationError]:
    old, new = choices.replace_spell, choices.replacement
    if old is None and new is None:
        return []
    bad = (
        old is None
        or new is None
        or old not in pc.spells_known
        or new not in pool
        or new in pc.spells_known
        or new in choices.spells
    )
    if bad:
        detail = f"cannot swap {old!r} for {new!r}"
        return [_err(_E.REPLACEMENT_INVALID, "replace_spell", detail)]
    return []


def _prepared_errors(
    pc: PcData,
    class_def: ClassDef,
    level: int,
    abilities: Mapping[Ability, int],
    choices: LevelUpChoices,
    pool: set[str],
) -> list[CreationError]:
    if choices.prepared is None:
        return []
    casting = class_def.spellcasting
    uses_book = casting is not None and casting.spellbook_start > 0
    allowed = set(pc.spellbook + choices.spells) & pool if uses_book else pool
    errors = pick_errors("prepared", choices.prepared, count=None, allowed=allowed)
    limit = prepared_spell_limit(class_def, level, abilities)
    if len(choices.prepared) > limit:
        detail = f"{len(choices.prepared)} prepared, the limit is {limit}"
        errors.append(_err(_E.PREPARED_OVER_LIMIT, "prepared", detail))
    return errors


def spell_learning_errors(
    pc: PcData,
    class_def: ClassDef,
    level: int,
    abilities: Mapping[Ability, int],
    choices: LevelUpChoices,
    regs: CharacterRegistries,
    feature_ids: Sequence[str],
    subclass: str | None,
) -> list[CreationError]:
    casting = class_def.spellcasting
    if casting is None or level < casting.first_level:
        return _no_picks_errors(choices)
    new_cantrips = cantrips_known_count(class_def, level) - cantrips_known_count(
        class_def, level - 1
    )
    cantrip_pool = class_spell_indexes(regs.spells, class_def.index, 0, 0)
    taken = pc.cantrips + pc.race_cantrips
    errors = pick_errors(
        "cantrips",
        choices.cantrips,
        count=pick_count(new_cantrips, cantrip_pool, taken),
        allowed=cantrip_pool,
        taken=taken,
    )
    pool = learnable_spells(class_def, level, feature_ids, subclass, regs)
    if casting.kind == "prepared":
        count = casting.spellbook_per_level if casting.spellbook_start else 0
        errors += pick_errors(
            "spells",
            choices.spells,
            count=pick_count(count, pool, pc.spellbook),
            allowed=pool,
            taken=pc.spellbook,
        )
        if choices.replace_spell or choices.replacement:
            errors.append(
                _err(_E.REPLACEMENT_INVALID, "replace_spell", "prepared casters swap by preparing")
            )
        return errors + _prepared_errors(pc, class_def, level, abilities, choices, pool)
    count = spells_known_count(class_def, level) - spells_known_count(class_def, level - 1)
    errors += pick_errors(
        "spells",
        choices.spells,
        count=pick_count(count, pool, pc.spells_known),
        allowed=pool,
        taken=pc.spells_known,
    )
    errors += _replacement_errors(pc, choices, pool)
    if choices.prepared is not None:
        errors.append(_err(_E.PICK_NOT_ALLOWED, "prepared", "known casters do not prepare"))
    return errors


def _prepared_list(
    pc: PcData, choices: LevelUpChoices, uses_book: bool, prepared_limit: int
) -> list[str]:
    if prepared_limit <= 0:
        return list(pc.prepared)
    book: list[str] = [*choices.spells, *pc.spellbook] if uses_book else []
    picked: list[str] = list(choices.prepared or [])
    merged = list(dict.fromkeys([*pc.prepared, *picked, *book]))
    return merged[: max(prepared_limit, len(pc.prepared))]


def learned_spell_lists(
    pc: PcData, class_def: ClassDef, choices: LevelUpChoices, prepared_limit: int
) -> LearnedSpells:
    casting = class_def.spellcasting
    uses_book = casting is not None and casting.spellbook_start > 0
    known = [choices.replacement if s == choices.replace_spell else s for s in pc.spells_known]
    known = [s for s in known if s is not None]
    return LearnedSpells(
        cantrips=[*pc.cantrips, *choices.cantrips],
        spells_known=known if uses_book else [*known, *choices.spells],
        spellbook=[*pc.spellbook, *choices.spells] if uses_book else list(pc.spellbook),
        prepared=_prepared_list(pc, choices, uses_book, prepared_limit),
    )
