"""Ability identifiers shared by every layer.

Public API:
- `Ability`: StrEnum of the six abilities. Values equal the SRD `ability_scores` index
  ("str", "dex", "con", "int", "wis", "cha"), so `Ability("dex")` parses SRD references directly.
- `ABILITIES`: the six abilities in canonical sheet order (STR, DEX, CON, INT, WIS, CHA).
- `Skill`: StrEnum of the 18 SRD skills. Values equal the SRD `skills` index
  ("animal-handling", "sleight-of-hand", ...), so `Skill(srd_index)` parses SRD references.
- `SKILL_ABILITY`: each skill's governing ability (SRD 5.1 "Using Each Ability"; a test verifies
  this constant against the vendored data/srd/skills.json).

The arithmetic (modifier, proficiency bonus) lives in `aidm.rules.abilities`.
"""

from enum import StrEnum


class Ability(StrEnum):
    STR = "str"
    DEX = "dex"
    CON = "con"
    INT = "int"
    WIS = "wis"
    CHA = "cha"


ABILITIES: tuple[Ability, ...] = tuple(Ability)


class Skill(StrEnum):
    ACROBATICS = "acrobatics"
    ANIMAL_HANDLING = "animal-handling"
    ARCANA = "arcana"
    ATHLETICS = "athletics"
    DECEPTION = "deception"
    HISTORY = "history"
    INSIGHT = "insight"
    INTIMIDATION = "intimidation"
    INVESTIGATION = "investigation"
    MEDICINE = "medicine"
    NATURE = "nature"
    PERCEPTION = "perception"
    PERFORMANCE = "performance"
    PERSUASION = "persuasion"
    RELIGION = "religion"
    SLEIGHT_OF_HAND = "sleight-of-hand"
    STEALTH = "stealth"
    SURVIVAL = "survival"


SKILL_ABILITY: dict[Skill, Ability] = {
    Skill.ACROBATICS: Ability.DEX,
    Skill.ANIMAL_HANDLING: Ability.WIS,
    Skill.ARCANA: Ability.INT,
    Skill.ATHLETICS: Ability.STR,
    Skill.DECEPTION: Ability.CHA,
    Skill.HISTORY: Ability.INT,
    Skill.INSIGHT: Ability.WIS,
    Skill.INTIMIDATION: Ability.CHA,
    Skill.INVESTIGATION: Ability.INT,
    Skill.MEDICINE: Ability.WIS,
    Skill.NATURE: Ability.INT,
    Skill.PERCEPTION: Ability.WIS,
    Skill.PERFORMANCE: Ability.CHA,
    Skill.PERSUASION: Ability.CHA,
    Skill.RELIGION: Ability.INT,
    Skill.SLEIGHT_OF_HAND: Ability.DEX,
    Skill.STEALTH: Ability.DEX,
    Skill.SURVIVAL: Ability.WIS,
}
