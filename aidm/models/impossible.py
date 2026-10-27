"""Impossible actions (M30.1, docs/next/GOAL_IMPOSSIBLE.md): the engine's verdict "cannot be done".

The DM model may declare a hero's action physically impossible (`request_check` with
`impossible`, `aidm.dm.tools`). The engine then rolls NO dice, so a natural 20 cannot rescue it,
and logs this event instead of a `CheckResolved`. It is NOT a seventh DC tier: `DcTier` and
`DC_BY_TIER` are unchanged.

Public API:
- `ActionImpossible(creature_id, text, reason)`: `text` is the attempt as told (the check's
  reason, else the player's words), `reason` why it cannot be done ("a person cannot jump onto
  a roof"). Log-only: THE reducer changes nothing but `GameState.event_count`. Part of
  `aidm.models.events.AnyEvent` (`ImpossibleEvents`).
- `LineRead(creature_id, text, steps, other)` (M43.1): how a TYPED line was read by the menu
  chooser: the engine actions it was mapped to (`steps`: one `entry` or `entry>target,target` per
  menu step) and whether part of it goes to the storyteller (`other`). Log-only like
  `ActionImpossible` (`scripts/contract.py` reads it); a refusal stays an `ActionImpossible`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_IMPOSSIBLE_TEXT = 200
MAX_IMPOSSIBLE_REASON = 120


class ActionImpossible(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["action_impossible"] = "action_impossible"
    creature_id: str = Field(min_length=1)
    text: str = Field(default="", max_length=MAX_IMPOSSIBLE_TEXT)
    reason: str = Field(min_length=1, max_length=MAX_IMPOSSIBLE_REASON)


MAX_READ_STEPS = 6
MAX_READ_STEP = 160


class LineRead(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["line_read"] = "line_read"
    creature_id: str = Field(min_length=1)
    text: str = Field(default="", max_length=MAX_IMPOSSIBLE_TEXT)
    steps: tuple[str, ...] = Field(default=(), max_length=MAX_READ_STEPS)
    other: bool = False


ImpossibleEvents = ActionImpossible | LineRead
