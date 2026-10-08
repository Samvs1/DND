"""The Scribe (M13.1, docs/next/GOAL_SCRIBE.md): the revive event and the public Scribe view.

Public API:
- `CharacterRewritten(target_id, payer_id, cost_gp, hp)`: a fallen hero was rewritten into the
  story. THE reducer sets the target alive with `hp`, death saves 0/0 and not stable. Gold and
  cleared conditions move through `GoldChanged` and `ConditionRemoved` before it. Part of
  `aidm.models.events.AnyEvent` (`ScribeEvents`).
- `FallenHero(creature_id, name, level, price_gp)`: one fallen hero and the Scribe's price.
- `ScribeView(available, reason, fallen)`: `PublicState.scribe`; `reason` is a refusal code
  (`scribe_in_combat`, `scribe_defeated`, `scribe_paused`, `scribe_none_fallen`) when the Scribe
  cannot revive anyone right now, else None.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CharacterRewritten(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["character_rewritten"] = "character_rewritten"
    target_id: str = Field(min_length=1)
    payer_id: str = Field(min_length=1)
    cost_gp: int = Field(ge=0)
    hp: int = Field(ge=1)


ScribeEvents = CharacterRewritten


class FallenHero(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    creature_id: str
    name: str
    level: int = Field(ge=1)
    price_gp: int = Field(ge=0)


class ScribeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool = False
    reason: str | None = None
    fallen: tuple[FallenHero, ...] = ()
