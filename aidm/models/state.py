"""Game state: the single mutable aggregate, changed ONLY by `aidm.session.reducer.apply`.

Public API:
- `CreatureKind`: PC / NPC / MONSTER.
- `ActiveCondition(name, source_id, duration, rounds_left, tick_on, tick_creature_id, save_ends)`:
  one condition instance on a creature (frozen). `name` is the key in data/bg3/conditions.json
  (SRD index, e.g. "prone"); `source_id` is the creature or effect that applied it.
  `duration` ROUNDS needs `rounds_left` (and only ROUNDS has it); `rounds_left` alone implies
  ROUNDS (old logs). A ROUNDS condition ticks at `tick_on` of `tick_creature_id`'s turn (None =
  the bearer's own turn). `save_ends` is re-rolled at the end of the bearer's turns.
  `persists_after_combat` (property): everything but ROUNDS survives the end of combat.
- `Creature`: one combatant or character, general enough for PCs, NPCs and monsters. Derived
  numbers (AC from armor, attack bonus, save DC) are computed by `aidm.rules`, not stored, unless a
  later checkpoint adds a base field with a default.
  Check inputs (M1.3): `proficiency_bonus` (PCs: from level at creation/level-up; monsters: the
  SRD value), `save_proficiencies`, `skill_proficiencies` and `skill_expertise` (expertise doubles
  the proficiency bonus and implies proficiency).
  Damage inputs (M1.4): `resistances`, `immunities`, `vulnerabilities` (damage types), and
  `death_saves`: None means "PCs make death saves at 0 HP, NPCs and monsters die"; True/False
  overrides that (an important NPC that should go down dying, a PC-like companion).
  Death state: `death_save_successes/failures`, `stable`, `dead`; dying = 0 HP, alive, unstable.
  Conditions (M1.5): `condition_immunities` (condition keys, e.g. SRD monster immunities) and
  `concentrating_on` (at most one `Concentration`).
- `GameState(campaign_id, seed, event_count, creatures)`: `event_count` is the number of events
  applied so far, so the session can use it as the next event `seq`.

Growth rule: every field added later MUST have a default, so snapshots and event logs written by
older builds still validate and replay. Models use `extra="forbid"` to catch typos early.
State models are deliberately NOT frozen and NOT `validate_assignment` (the reducer mutates them in
place for speed); they validate fully when constructed or loaded from JSON.
"""

from enum import StrEnum
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.models.abilities import Ability, Skill
from aidm.models.conditions import Concentration, ConditionDuration, SaveEnds, TurnBoundary
from aidm.models.damage import DamageType


class CreatureKind(StrEnum):
    PC = "pc"
    NPC = "npc"
    MONSTER = "monster"


class ActiveCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    source_id: str | None = None
    duration: ConditionDuration = ConditionDuration.UNTIL_REMOVED
    rounds_left: int | None = Field(default=None, ge=0)
    tick_on: TurnBoundary = TurnBoundary.END_OF_TURN
    tick_creature_id: str | None = None
    save_ends: SaveEnds | None = None

    @model_validator(mode="before")
    @classmethod
    def _infer_rounds(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        raw = cast(dict[str, object], data)
        if raw.get("rounds_left") is not None and "duration" not in raw:
            return {**raw, "duration": ConditionDuration.ROUNDS}
        return raw

    @model_validator(mode="after")
    def _check_duration(self) -> "ActiveCondition":
        has_rounds = self.rounds_left is not None
        if has_rounds != (self.duration is ConditionDuration.ROUNDS):
            raise ValueError("rounds_left is required for, and only for, a ROUNDS duration")
        return self

    @property
    def persists_after_combat(self) -> bool:
        return self.duration is not ConditionDuration.ROUNDS


def _default_abilities() -> dict[Ability, int]:
    return dict.fromkeys(Ability, 10)


class Creature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: CreatureKind
    abilities: dict[Ability, int] = Field(default_factory=_default_abilities)
    max_hp: int = Field(ge=1)
    hp: int = Field(ge=0)
    temp_hp: int = Field(default=0, ge=0)
    ac: int = Field(default=10, ge=0)
    proficiency_bonus: int = Field(default=2, ge=0, le=10)
    save_proficiencies: list[Ability] = Field(default_factory=list[Ability])
    skill_proficiencies: list[Skill] = Field(default_factory=list[Skill])
    skill_expertise: list[Skill] = Field(default_factory=list[Skill])
    resistances: list[DamageType] = Field(default_factory=list[DamageType])
    immunities: list[DamageType] = Field(default_factory=list[DamageType])
    vulnerabilities: list[DamageType] = Field(default_factory=list[DamageType])
    death_saves: bool | None = None
    conditions: list[ActiveCondition] = Field(default_factory=list[ActiveCondition])
    condition_immunities: list[str] = Field(default_factory=list[str])
    concentrating_on: Concentration | None = None
    death_save_successes: int = Field(default=0, ge=0, le=3)
    death_save_failures: int = Field(default=0, ge=0, le=3)
    stable: bool = False
    dead: bool = False

    @model_validator(mode="after")
    def _check_hp(self) -> "Creature":
        if self.hp > self.max_hp:
            raise ValueError(f"hp {self.hp} exceeds max_hp {self.max_hp}")
        return self


class GameState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str = Field(min_length=1)
    seed: int
    event_count: int = Field(default=0, ge=0)
    creatures: dict[str, Creature] = Field(default_factory=dict[str, Creature])
