"""Table difficulty (M6.5): multipliers for hostile monsters, stored in `GameState.difficulty`.

`monster_hp` scales the hit points of hostile monsters spawned from then on (at encounter start);
`monster_damage` scales the damage they deal (the damage choke in `aidm.rules.attacks`). 1.0 is
the SRD default. Changed only by the `DifficultySet` campaign event.
"""

from pydantic import BaseModel, ConfigDict, Field

MIN_MULTIPLIER = 0.25
MAX_MULTIPLIER = 3.0


class Difficulty(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    monster_hp: float = Field(default=1.0, ge=MIN_MULTIPLIER, le=MAX_MULTIPLIER)
    monster_damage: float = Field(default=1.0, ge=MIN_MULTIPLIER, le=MAX_MULTIPLIER)
