"""Ability score arithmetic.

Public API:
- `ability_modifier(score) -> int`: floor((score - 10) / 2), SRD 5.1 "Ability Scores and
  Modifiers" table (1 -> -5, 10 -> +0, 30 -> +10). Scores outside 1..30 raise ValueError.
- `proficiency_bonus(level) -> int`: 2 + (level - 1) // 4, SRD 5.1 class tables
  (1-4: +2, 5-8: +3, 9-12: +4, 13-16: +5, 17-20: +6). Levels outside 1..20 raise ValueError.
  Monsters use their SRD `proficiency_bonus` field instead of this function.
"""

MIN_SCORE = 1
MAX_SCORE = 30
MIN_LEVEL = 1
MAX_CLASS_LEVEL = 20


def ability_modifier(score: int) -> int:
    if not MIN_SCORE <= score <= MAX_SCORE:
        raise ValueError(f"ability score {score} outside {MIN_SCORE}..{MAX_SCORE}")
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    if not MIN_LEVEL <= level <= MAX_CLASS_LEVEL:
        raise ValueError(f"level {level} outside {MIN_LEVEL}..{MAX_CLASS_LEVEL}")
    return 2 + (level - 1) // 4
