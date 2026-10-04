"""Typed d20 test results: ability checks, skill checks and saving throws.

Public API:
- `DcTier`: the six difficulty tiers the AI may request (SPEC 6.3 `dc_tier`). The engine maps
  them to numbers in `aidm.rules.checks.dc_for_tier` (5, 10, 15, 20, 25, 30).
- `CheckKind`: ABILITY / SKILL / SAVE.
- `CheckResult(kind, ability, skill, roll, dc, success, margin)`: a resolved test. `margin` is
  `roll.total - dc` (>= 0 means the total met the DC). `success` can differ from `margin >= 0`
  only through the natural 20 / natural 1 rule for checks (see docs/RULES_DECISIONS.md).

Frozen so a result can be embedded in a `CheckResolved` event.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.abilities import Ability, Skill
from aidm.models.dice import D20Roll


class DcTier(StrEnum):
    TRIVIAL = "trivial"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    VERY_HARD = "very_hard"
    NEARLY_IMPOSSIBLE = "nearly_impossible"


class CheckKind(StrEnum):
    ABILITY = "ability"
    SKILL = "skill"
    SAVE = "save"


class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: CheckKind
    ability: Ability
    skill: Skill | None = None
    roll: D20Roll
    dc: int = Field(ge=0)
    success: bool
    margin: int
