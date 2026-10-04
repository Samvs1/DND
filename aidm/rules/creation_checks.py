"""Per-step validation for character creation; `aidm.rules.creation` composes these.

Every check returns typed `CreationError`s and never raises for a user mistake.

Public API:
- `CreationRefs(race, subrace, cls, background)`: the resolved data entries of a choice set.
- `resolve_refs(choices, regs) -> (CreationRefs | None, errors)`: looks up race, subrace, class
  and background; a race with subraces requires one (all SRD subraced races have exactly one).
- `pick_errors(field, picks, *, count, allowed, taken=()) -> errors`: the generic "choose N of
  these" check: wrong count (None = any count), duplicates, already granted elsewhere, or not
  offered (`allowed` None = anything).
- `granted_skills(refs)`, `granted_tools(refs)`, `granted_languages(refs)`: what the race,
  subrace, class (tools) and background give without a pick, in grant order.
- `class_spell_indexes(spells, class_index, min_level, max_level) -> set[str]`: SRD class list.
- `skill_tool_language_errors(choices, refs, regs)`, `equipment_errors(choices, refs)`,
  `class_choice_errors(choices, refs, level)`, `text_errors(choices)`.
- `MAX_NAME_CHARS` (40), `MAX_PRONOUN_CHARS` (30), `MAX_PORTRAIT_ID_CHARS` (64).
"""

from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from aidm.data.background_defs import BackgroundDef
from aidm.data.character_data import CharacterRegistries
from aidm.data.class_defs import ClassDef
from aidm.data.race_defs import RaceDef, SubraceDef
from aidm.data.registry import Registry
from aidm.data.srd_spells import SrdSpell
from aidm.models.abilities import Skill
from aidm.models.character import MAX_BACKSTORY_CHARS
from aidm.models.creation import CreationChoices, CreationError, CreationErrorCode

MAX_NAME_CHARS = 40
MAX_PRONOUN_CHARS = 30
MAX_PORTRAIT_ID_CHARS = 64
_E = CreationErrorCode


@dataclass(frozen=True)
class CreationRefs:
    race: RaceDef
    subrace: SubraceDef | None
    cls: ClassDef
    background: BackgroundDef


def _err(code: CreationErrorCode, field: str, detail: str) -> CreationError:
    return CreationError(code=code, field=field, detail=detail)


def _subrace(
    race: RaceDef, choices: CreationChoices
) -> tuple[SubraceDef | None, list[CreationError]]:
    if choices.subrace is None:
        if race.subraces:
            return None, [_err(_E.SUBRACE_REQUIRED, "subrace", f"{race.index} needs a subrace")]
        return None, []
    found = next((s for s in race.subraces if s.index == choices.subrace), None)
    if found is None:
        detail = f"{choices.subrace!r} is not a subrace of {race.index}"
        return None, [_err(_E.UNKNOWN_SUBRACE, "subrace", detail)]
    return found, []


def resolve_refs(
    choices: CreationChoices, regs: CharacterRegistries
) -> tuple[CreationRefs | None, list[CreationError]]:
    errors: list[CreationError] = []
    race = regs.races.find(choices.race)
    subrace: SubraceDef | None = None
    if race is None:
        errors.append(_err(_E.UNKNOWN_RACE, "race", f"unknown race {choices.race!r}"))
    else:
        subrace, sub_errors = _subrace(race, choices)
        errors.extend(sub_errors)
    cls = regs.classes.find(choices.class_index)
    if cls is None:
        detail = f"unknown class {choices.class_index!r}"
        errors.append(_err(_E.UNKNOWN_CLASS, "class_index", detail))
    background = regs.backgrounds.find(choices.background)
    if background is None:
        detail = f"unknown background {choices.background!r}"
        errors.append(_err(_E.UNKNOWN_BACKGROUND, "background", detail))
    if errors or race is None or cls is None or background is None:
        return None, errors
    return CreationRefs(race=race, subrace=subrace, cls=cls, background=background), []


def pick_errors(
    field: str,
    picks: Sequence[str],
    *,
    count: int | None,
    allowed: Collection[str] | None,
    taken: Collection[str] = (),
) -> list[CreationError]:
    errors: list[CreationError] = []
    if count is not None and len(picks) != count:
        errors.append(_err(_E.PICK_COUNT, field, f"choose exactly {count}, got {len(picks)}"))
    dupes = sorted(p for p, n in Counter(picks).items() if n > 1)
    clashes = sorted({p for p in picks if p in taken})
    if dupes or clashes:
        errors.append(
            _err(_E.PICK_DUPLICATE, field, f"picked twice or already granted: {dupes + clashes}")
        )
    if allowed is not None:
        bad = sorted({p for p in picks if p not in allowed})
        if bad:
            errors.append(_err(_E.PICK_NOT_ALLOWED, field, f"not offered here: {bad}"))
    return errors


def _both[T](race_part: tuple[T, ...], sub_part: tuple[T, ...] | None) -> list[T]:
    return list(race_part) + (list(sub_part) if sub_part is not None else [])


def _dedupe(items: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(items))


def granted_skills(refs: CreationRefs) -> list[str]:
    sub = refs.subrace.skills if refs.subrace else None
    return _dedupe(list(refs.background.skills) + _both(refs.race.skills, sub))


def granted_tools(refs: CreationRefs) -> list[str]:
    sub = refs.subrace.tool_proficiencies if refs.subrace else None
    race_tools = _both(refs.race.tool_proficiencies, sub)
    return _dedupe(list(refs.cls.tools) + race_tools + list(refs.background.tools))


def granted_languages(refs: CreationRefs) -> list[str]:
    sub = refs.subrace.languages if refs.subrace else None
    return _dedupe(_both(refs.race.languages, sub))


def class_spell_indexes(
    spells: Registry[SrdSpell], class_index: str, min_level: int, max_level: int
) -> set[str]:
    return {
        s.index
        for s in spells.all()
        if min_level <= s.level <= max_level and any(c.index == class_index for c in s.classes)
    }


def skill_tool_language_errors(
    choices: CreationChoices, refs: CreationRefs, regs: CharacterRegistries
) -> list[CreationError]:
    granted = granted_skills(refs)
    skill_list = refs.cls.skill_choice
    errors = pick_errors(
        "class_skills",
        choices.class_skills,
        count=skill_list.choose,
        allowed=skill_list.options,
        taken=granted,
    )
    race_list = refs.race.skill_choice
    errors += pick_errors(
        "race_skills",
        choices.race_skills,
        count=race_list.choose if race_list else 0,
        allowed=race_list.options if race_list else (),
        taken=granted + choices.class_skills,
    )
    tool_list = refs.race.tool_choice or (refs.subrace.tool_choice if refs.subrace else None)
    errors += pick_errors(
        "tool_picks",
        choices.tool_picks,
        count=tool_list.choose if tool_list else 0,
        allowed=tool_list.options if tool_list else (),
        taken=granted_tools(refs),
    )
    sub_langs = refs.subrace.language_choices if refs.subrace else 0
    errors += pick_errors(
        "language_picks",
        choices.language_picks,
        count=refs.race.language_choices + sub_langs,
        allowed=[lang.index for lang in regs.languages.all()],
        taken=granted_languages(refs),
    )
    errors += _skill_index_errors(choices.class_skills + choices.race_skills)
    return errors


def _skill_index_errors(picks: Sequence[str]) -> list[CreationError]:
    known = {s.value for s in Skill}
    bad = sorted({p for p in picks if p not in known})
    if bad:
        return [_err(_E.PICK_NOT_ALLOWED, "skills", f"unknown skills {bad}")]
    return []


def equipment_errors(choices: CreationChoices, refs: CreationRefs) -> list[CreationError]:
    errors: list[CreationError] = []
    offered = {c.id: c for c in refs.cls.equipment.choices}
    for choice_id, choice in offered.items():
        index = choices.equipment_picks.get(choice_id)
        if index is None:
            errors.append(_err(_E.EQUIPMENT_MISSING, f"equipment_picks.{choice_id}", "pick one"))
        elif not 0 <= index < len(choice.options):
            detail = f"option {index} not in 0..{len(choice.options) - 1}"
            errors.append(_err(_E.EQUIPMENT_INVALID, f"equipment_picks.{choice_id}", detail))
    for choice_id in sorted(set(choices.equipment_picks) - set(offered)):
        detail = f"{refs.cls.index} has no equipment choice {choice_id!r}"
        errors.append(_err(_E.EQUIPMENT_INVALID, f"equipment_picks.{choice_id}", detail))
    return errors


def class_choice_errors(
    choices: CreationChoices, refs: CreationRefs, level: int
) -> list[CreationError]:
    errors: list[CreationError] = []
    due = {c.id: c for c in refs.cls.choices if c.level <= level}
    for choice_id, choice in due.items():
        picks = choices.class_choices.get(choice_id, [])
        errors += pick_errors(
            f"class_choices.{choice_id}",
            picks,
            count=choice.pick.choose,
            allowed=choice.pick.options,
        )
    for choice_id in sorted(set(choices.class_choices) - set(due)):
        detail = f"no class choice {choice_id!r} at level {level}"
        errors.append(_err(_E.PICK_NOT_ALLOWED, f"class_choices.{choice_id}", detail))
    return errors


def text_errors(choices: CreationChoices) -> list[CreationError]:
    errors: list[CreationError] = []
    name = choices.name.strip()
    if not name or len(name) > MAX_NAME_CHARS:
        detail = f"a name needs 1..{MAX_NAME_CHARS} characters"
        errors.append(_err(_E.NAME_INVALID, "name", detail))
    limits = (
        ("pronouns", choices.pronouns, MAX_PRONOUN_CHARS),
        ("backstory", choices.backstory, MAX_BACKSTORY_CHARS),
        ("portrait_id", choices.portrait_id, MAX_PORTRAIT_ID_CHARS),
    )
    for field, text, limit in limits:
        if len(text) > limit:
            detail = f"{len(text)} characters, at most {limit}"
            errors.append(_err(_E.TEXT_TOO_LONG, field, detail))
    return errors
