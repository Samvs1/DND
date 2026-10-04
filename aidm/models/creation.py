"""Character-creation input and its typed validation errors (SPEC 8).

`CreationChoices` is what the wizard sends: every pick a level-1 character needs. Its fields are
deliberately loose (plain strings and lists): semantic mistakes (overspent point buy, an unknown
race, a skill the class does not offer, a long backstory) are reported by
`aidm.rules.creation.validate_creation` as `CreationError`s, never raised.

Public API:
- `AbilityMethod`: POINT_BUY / STANDARD_ARRAY / ROLL_4D6.
- `CreationChoices`: identity text (`name`, `pronouns`, `backstory`, `portrait_id`), `race`,
  `subrace`, `class_index`, `background`; ability scores: `ability_method`, `base_scores` (before
  racial bonuses), `rolls` (the six "4d6kh3" rolls for ROLL_4D6, shown to the player; the scores
  must be an assignment of their totals), `ability_choice_picks` (half-elf style +1 picks); picks:
  `class_skills`, `race_skills`, `tool_picks`, `language_picks`, `equipment_picks` (class choice
  id -> option index), `class_choices` (class choice id -> option ids, e.g. a fighting style),
  `feature_choices` (feature id -> picks: expertise skills, a draconic ancestry option);
  spells: `cantrips` (class), `race_cantrips` (high elf), `spells` (known spells, or a wizard's
  spellbook), `prepared` (prepared casters).
- `CreationErrorCode`, `CreationError(code, field, detail)`: one problem with one field.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.abilities import Ability
from aidm.models.dice import Roll


class AbilityMethod(StrEnum):
    POINT_BUY = "point_buy"
    STANDARD_ARRAY = "standard_array"
    ROLL_4D6 = "roll_4d6"


class CreationChoices(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = ""
    pronouns: str = ""
    backstory: str = ""
    portrait_id: str = ""
    race: str
    subrace: str | None = None
    class_index: str
    background: str
    ability_method: AbilityMethod
    base_scores: dict[Ability, int] = Field(default_factory=dict[Ability, int])
    rolls: list[Roll] = Field(default_factory=list[Roll])
    ability_choice_picks: list[Ability] = Field(default_factory=list[Ability])
    class_skills: list[str] = Field(default_factory=list[str])
    race_skills: list[str] = Field(default_factory=list[str])
    tool_picks: list[str] = Field(default_factory=list[str])
    language_picks: list[str] = Field(default_factory=list[str])
    equipment_picks: dict[str, int] = Field(default_factory=dict[str, int])
    class_choices: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    feature_choices: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    cantrips: list[str] = Field(default_factory=list[str])
    race_cantrips: list[str] = Field(default_factory=list[str])
    spells: list[str] = Field(default_factory=list[str])
    prepared: list[str] = Field(default_factory=list[str])


class CreationErrorCode(StrEnum):
    UNKNOWN_RACE = "unknown_race"
    UNKNOWN_SUBRACE = "unknown_subrace"
    SUBRACE_REQUIRED = "subrace_required"
    UNKNOWN_CLASS = "unknown_class"
    UNKNOWN_BACKGROUND = "unknown_background"
    ABILITY_MISSING = "ability_missing"
    SCORE_OUT_OF_RANGE = "score_out_of_range"
    POINT_BUY_OVERSPEND = "point_buy_overspend"
    STANDARD_ARRAY_MISMATCH = "standard_array_mismatch"
    ROLLS_INVALID = "rolls_invalid"
    ROLL_ASSIGNMENT_MISMATCH = "roll_assignment_mismatch"
    PICK_COUNT = "pick_count"
    PICK_NOT_ALLOWED = "pick_not_allowed"
    PICK_DUPLICATE = "pick_duplicate"
    EQUIPMENT_MISSING = "equipment_missing"
    EQUIPMENT_INVALID = "equipment_invalid"
    PREPARED_OVER_LIMIT = "prepared_over_limit"
    NAME_INVALID = "name_invalid"
    TEXT_TOO_LONG = "text_too_long"


class CreationError(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: CreationErrorCode
    field: str
    detail: str
