"""Typed SRD character-building entries: races, classes, levels, traits and misc lists."""

from __future__ import annotations

from pydantic import Field, JsonValue

from aidm.data.srd_common import ApiRef, SrdModel


class AbilityBonus(SrdModel):
    ability_score: ApiRef
    bonus: int


class SrdRace(SrdModel):
    index: str
    name: str
    speed: int
    size: str
    ability_bonuses: list[AbilityBonus] = []
    ability_bonus_options: JsonValue | None = None
    languages: list[ApiRef] = []
    language_options: JsonValue | None = None
    traits: list[ApiRef] = []
    subraces: list[ApiRef] = []
    alignment: str = ""
    age: str = ""
    size_description: str = ""


class SrdSubrace(SrdModel):
    index: str
    name: str
    race: ApiRef
    desc: str = ""
    ability_bonuses: list[AbilityBonus] = []
    racial_traits: list[ApiRef] = []


class SrdClass(SrdModel):
    index: str
    name: str
    hit_die: int
    proficiencies: list[ApiRef]
    saving_throws: list[ApiRef]
    proficiency_choices: list[JsonValue] = []
    starting_equipment: list[JsonValue] = []
    starting_equipment_options: list[JsonValue] = []
    subclasses: list[ApiRef] = []
    spellcasting: JsonValue | None = None
    multi_classing: JsonValue | None = None


class SrdLevel(SrdModel):
    """One class (or subclass) level row; subclass rows omit prof_bonus."""

    index: str
    level: int
    class_ref: ApiRef = Field(alias="class")
    subclass: ApiRef | None = None
    ability_score_bonuses: int | None = None
    prof_bonus: int | None = None
    features: list[ApiRef] = []
    spellcasting: dict[str, int] | None = None
    class_specific: JsonValue | None = None
    subclass_specific: JsonValue | None = None


class SrdSubclass(SrdModel):
    index: str
    name: str
    class_ref: ApiRef = Field(alias="class")
    subclass_flavor: str = ""
    desc: list[str] = []
    spells: list[JsonValue] = []


class SrdFeature(SrdModel):
    index: str
    name: str
    level: int
    class_ref: ApiRef = Field(alias="class")
    subclass: ApiRef | None = None
    parent: ApiRef | None = None
    prerequisites: list[JsonValue] = []
    desc: list[str] = []
    feature_specific: JsonValue | None = None


class SrdTrait(SrdModel):
    index: str
    name: str
    desc: list[str] = []
    races: list[ApiRef] = []
    subraces: list[ApiRef] = []
    proficiencies: list[ApiRef] = []
    parent: ApiRef | None = None
    proficiency_choices: JsonValue | None = None
    language_options: JsonValue | None = None
    trait_specific: JsonValue | None = None


class SrdCondition(SrdModel):
    index: str
    name: str
    desc: list[str]


class SrdSkill(SrdModel):
    index: str
    name: str
    desc: list[str] = []
    ability_score: ApiRef


class SrdLanguage(SrdModel):
    index: str
    name: str
    type: str


class SrdDamageType(SrdModel):
    index: str
    name: str
    desc: list[str] = []


class SrdProficiency(SrdModel):
    index: str
    name: str
    type: str
    classes: list[ApiRef] = []
    races: list[ApiRef] = []
    reference: ApiRef | None = None


class SrdBackground(SrdModel):
    index: str
    name: str
    starting_proficiencies: list[ApiRef] = []
    language_options: JsonValue | None = None
    starting_equipment: list[JsonValue] = []
    starting_equipment_options: list[JsonValue] = []
    starting_gold: JsonValue | None = None
    feature: JsonValue | None = None
    personality_traits: JsonValue | None = None
    ideals: JsonValue | None = None
    bonds: JsonValue | None = None
    flaws: JsonValue | None = None
