"""Small English helpers for engine-made lines: articles and the display names of checks.

Event lines and template narration name checks the same way ("an Investigation check",
"a Dexterity save"), so the wording lives here once.

Public API: `with_article(phrase)`, `ABILITY_NAMES`, `skill_name(skill)`, `check_subject(result)`.
"""

from aidm.models.abilities import Ability, Skill
from aidm.models.checks import CheckResult

ABILITY_NAMES: dict[Ability, str] = {
    Ability.STR: "Strength",
    Ability.DEX: "Dexterity",
    Ability.CON: "Constitution",
    Ability.INT: "Intelligence",
    Ability.WIS: "Wisdom",
    Ability.CHA: "Charisma",
}
_SMALL_WORDS = frozenset({"of", "and", "the"})


def with_article(phrase: str) -> str:
    """'an Investigation check', 'a Stealth check' (vowel-letter rule; enough for our words)."""
    word = phrase.strip()
    article = "an" if word[:1].lower() in "aeiou" else "a"
    return f"{article} {word}"


def skill_name(skill: Skill) -> str:
    words = skill.value.replace("-", " ").split()
    return " ".join(w if i and w in _SMALL_WORDS else w.capitalize() for i, w in enumerate(words))


def check_subject(result: CheckResult) -> str:
    """The capitalised name of what was tested: a skill, else the ability's full name."""
    if result.skill is not None:
        return skill_name(result.skill)
    return ABILITY_NAMES[result.ability]
