"""The tiers the AI may pick; the engine maps each to numbers (SPEC 2.1, 6.3).

Public API:
- `Severity`: minor / moderate / major (creative effects: damage dice, save DC and duration by
  party level, `aidm.rules.dm_tiers`).
- `XpTier`: minor / moderate / major (XP per PC by party level).
- `DeltaTier`: the social attitude steps of `update_attitude` (`aidm.rules.social`).
- `EffectKind`: what a `creative_effect` does (damage, a condition, zone terrain/light, an
  advantage, a push).
- `AttitudeBand`: hostile / unfriendly / indifferent / friendly / ally (from the score).
"""

from enum import StrEnum


class Severity(StrEnum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"


class XpTier(StrEnum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"


class DeltaTier(StrEnum):
    WORSEN_MAJOR = "worsen_major"
    WORSEN = "worsen"
    WORSEN_SLIGHT = "worsen_slight"
    IMPROVE_SLIGHT = "improve_slight"
    IMPROVE = "improve"
    IMPROVE_MAJOR = "improve_major"


class EffectKind(StrEnum):
    MINOR_DAMAGE = "minor_damage"
    CONDITION = "condition"
    DIFFICULT_TERRAIN = "difficult_terrain"
    ADVANTAGE_NEXT_ATTACK = "advantage_next_attack"
    PUSH = "push"
    LIGHT = "light"
    DARK = "dark"


class AttitudeBand(StrEnum):
    HOSTILE = "hostile"
    UNFRIENDLY = "unfriendly"
    INDIFFERENT = "indifferent"
    FRIENDLY = "friendly"
    ALLY = "ally"
