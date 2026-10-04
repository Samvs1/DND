"""Default (valid) creation choices for any class x race x subrace, shared by creation tests."""

from __future__ import annotations

from aidm.data.character_data import CharacterRegistries, character_registries
from aidm.models.abilities import ABILITIES, Ability
from aidm.models.creation import AbilityMethod, CreationChoices
from aidm.rules.ability_gen import STANDARD_ARRAY
from aidm.rules.creation_checks import (
    CreationRefs,
    class_spell_indexes,
    granted_languages,
    granted_skills,
    granted_tools,
)


def race_combos() -> list[tuple[str, str | None]]:
    combos: list[tuple[str, str | None]] = []
    for race in character_registries().races.all():
        if race.subraces:
            combos.extend((race.index, sub.index) for sub in race.subraces)
        else:
            combos.append((race.index, None))
    return combos


def _first(options: tuple[str, ...] | list[str], n: int, exclude: list[str]) -> list[str]:
    return [o for o in options if o not in exclude][:n]


def _sorted_spells(regs: CharacterRegistries, cls: str, lo: int, hi: int) -> list[str]:
    return sorted(class_spell_indexes(regs.spells, cls, lo, hi))


def _spell_picks(regs: CharacterRegistries, refs: CreationRefs) -> dict[str, list[str]]:
    cls = refs.cls
    row = cls.level(1)
    cantrips = _sorted_spells(regs, cls.index, 0, 0)[: row.cantrips_known]
    picks: dict[str, list[str]] = {"cantrips": cantrips, "spells": [], "prepared": []}
    casting = cls.spellcasting
    if casting is not None and casting.first_level == 1:
        level1 = _sorted_spells(regs, cls.index, 1, 1)
        if casting.kind == "prepared":
            picks["spells"] = level1[: casting.spellbook_start]
            picks["prepared"] = level1[:1]
        else:
            picks["spells"] = level1[: row.spells_known or 0]
    race_class = refs.race.cantrip_class or (refs.subrace.cantrip_class if refs.subrace else None)
    if race_class:
        count = refs.race.cantrip_choices + (refs.subrace.cantrip_choices if refs.subrace else 0)
        pool = _sorted_spells(regs, race_class, 0, 0)
        picks["race_cantrips"] = _first(pool, count, cantrips)
    return picks


def default_choices(class_index: str, race_index: str, subrace: str | None) -> CreationChoices:
    """Valid level-1 choices: standard array in sheet order, first legal option everywhere."""
    regs = character_registries()
    race = regs.races.get(race_index)
    sub = next((s for s in race.subraces if s.index == subrace), None)
    cls = regs.classes.get(class_index)
    background = regs.backgrounds.all()[0]
    refs = CreationRefs(race=race, subrace=sub, cls=cls, background=background)
    granted = granted_skills(refs)
    class_skills = _first(cls.skill_choice.options, cls.skill_choice.choose, granted)
    race_skills: list[str] = []
    if race.skill_choice:
        taken = granted + class_skills
        race_skills = _first(race.skill_choice.options, race.skill_choice.choose, taken)
    tools: list[str] = []
    tool_list = race.tool_choice or (sub.tool_choice if sub else None)
    if tool_list:
        tools = _first(tool_list.options, tool_list.choose, granted_tools(refs))
    lang_count = race.language_choices + (sub.language_choices if sub else 0)
    all_langs = [lang.index for lang in regs.languages.all()]
    languages = _first(all_langs, lang_count, granted_languages(refs))
    picks: list[Ability] = []
    if race.ability_choice:
        picks = [Ability(a) for a in race.ability_choice.options[: race.ability_choice.choose]]
    spells = _spell_picks(regs, refs)
    return CreationChoices(
        name="Test Hero",
        race=race_index,
        subrace=subrace,
        class_index=class_index,
        background=background.index,
        ability_method=AbilityMethod.STANDARD_ARRAY,
        base_scores=dict(zip(ABILITIES, STANDARD_ARRAY, strict=True)),
        ability_choice_picks=picks,
        class_skills=class_skills,
        race_skills=race_skills,
        tool_picks=tools,
        language_picks=languages,
        equipment_picks={c.id: 0 for c in cls.equipment.choices},
        class_choices={
            c.id: list(c.pick.options[: c.pick.choose]) for c in cls.choices if c.level <= 1
        },
        cantrips=spells.get("cantrips", []),
        race_cantrips=spells.get("race_cantrips", []),
        spells=spells.get("spells", []),
        prepared=spells.get("prepared", []),
    )
