"""Level-up input (SPEC 7.2, 7.5): the player's picks for ONE level gained.

Problems are reported by `aidm.rules.leveling.validate_level_up` as `CreationError`s (shared
with creation so the wizard maps both the same way); nothing is raised for a user mistake.

Public API:
- `LevelUpChoices`: `subclass` (required exactly at the class's subclass level, and only then),
  `class_choices` (class choice id -> option ids due at this level, e.g. a ranger fighting
  style), `feature_choices` (feature id -> picks for features gained now), `asi` (ability ->
  increase at an Ability Score Improvement level: +2 to one or +1 to two, scores capped at 20;
  feats are out of scope), `cantrips` (new cantrips), `spells` (known/pact casters: newly
  learned spells; spellbook casters: spells added to the book), `replace_spell` +
  `replacement` (a known/pact caster may swap one known spell), `prepared` (prepared casters:
  the new prepared list, None keeps the current one).
"""

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.abilities import Ability


class LevelUpChoices(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subclass: str | None = None
    class_choices: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    feature_choices: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    asi: dict[Ability, int] = Field(default_factory=dict[Ability, int])
    cantrips: list[str] = Field(default_factory=list[str])
    spells: list[str] = Field(default_factory=list[str])
    replace_spell: str | None = None
    replacement: str | None = None
    prepared: list[str] | None = None
