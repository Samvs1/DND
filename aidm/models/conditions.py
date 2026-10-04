"""Typed pieces of condition instances and concentration (pure data, no rules here).

Public API:
- `ConditionDuration`: ROUNDS (counts down at turn boundaries), UNTIL_LONG_REST (ends on a long
  rest, e.g. exhaustion), UNTIL_REMOVED (ends only when an effect or rule removes it: the 0-HP
  unconscious condition, a spell ended by concentration).
- `TurnBoundary`: START_OF_TURN / END_OF_TURN, the moment a ROUNDS duration ticks down.
- `SaveEnds(ability, dc)`: the bearer repeats this saving throw at the end of each of its turns;
  a success removes the condition (SRD 5.1 spells such as Hold Person).
- `ConditionLink(creature_id, name)`: a condition the concentrating creature applied (with
  `source_id` = the concentrating creature) to `creature_id`; it ends with the concentration.
- `Concentration(spell_id, links)`: the ONE effect a creature concentrates on (SRD 5.1
  "Concentration": a new concentration effect ends the previous one).

All models are frozen so they can be embedded in events and shared safely.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.abilities import Ability


class ConditionDuration(StrEnum):
    ROUNDS = "rounds"
    UNTIL_LONG_REST = "until_long_rest"
    UNTIL_REMOVED = "until_removed"


class TurnBoundary(StrEnum):
    START_OF_TURN = "start_of_turn"
    END_OF_TURN = "end_of_turn"


class SaveEnds(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ability: Ability
    dc: int = Field(ge=0)


class ConditionLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    creature_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class Concentration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    spell_id: str = Field(min_length=1)
    links: tuple[ConditionLink, ...] = ()
