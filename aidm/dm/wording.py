"""Small English helpers for engine-made lines: articles and the display names of checks.

Event lines and template narration name checks the same way ("an Investigation check",
"a Dexterity save"), so the wording lives here once.

Counting foes (M20.6, playtest 3: two rats were "a giant rat"): `plural(noun)` ("goblins",
"swarms of bats", "wolves"), `counted(noun, n, digits=False)` ("a goblin", "two giant rats", or
"2 giant rats" for the model).

Public API: `with_article(phrase)`, `plural(noun)`, `counted(noun, n, digits=False)`,
`ABILITY_NAMES`, `skill_name(skill)`, `check_subject(result)`.
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


_NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_IRREGULAR = {
    "wolf": "wolves",
    "elf": "elves",
    "dwarf": "dwarves",
    "thief": "thieves",
    "ox": "oxen",
}


def plural(noun: str) -> str:
    head, sep, tail = noun.partition(" of ")
    words = head.split(" ")
    last, low = words[-1], words[-1].lower()
    if low in _IRREGULAR:
        last = _IRREGULAR[low].capitalize() if last[:1].isupper() else _IRREGULAR[low]
    elif low.endswith(("s", "x", "ch", "sh")):
        last += "es"
    elif low.endswith("y") and low[-2:-1] not in ("a", "e", "i", "o", "u"):
        last = last[:-1] + "ies"
    elif low.endswith("man"):
        last = last[:-3] + "men"
    else:
        last += "s"
    return " ".join([*words[:-1], last]) + (sep + tail if sep else "")


def counted(noun: str, n: int, *, digits: bool = False) -> str:
    if n == 1:
        return with_article(noun)
    word = str(n) if digits or n >= len(_NUMBER_WORDS) else _NUMBER_WORDS[n]
    return f"{word} {plural(noun)}"


def skill_name(skill: Skill) -> str:
    words = skill.value.replace("-", " ").split()
    return " ".join(w if i and w in _SMALL_WORDS else w.capitalize() for i, w in enumerate(words))


def check_subject(result: CheckResult) -> str:
    """The capitalised name of what was tested: a skill, else the ability's full name."""
    if result.skill is not None:
        return skill_name(result.skill)
    return ABILITY_NAMES[result.ability]
