"""Encounter events (part of the `aidm.models.events.Event` union; same design rules apply).

Every payload is resolved: initiative rolls, the per-turn economy and the XP split are computed
by `aidm.rules` and only assigned by the reducer.

Public API:
- `EncounterStarted(encounter)`: the full initial `Encounter` (combatants with zones and
  economy, sorted initiative, round 1, `active_index` -1). Monsters were added by the
  `CreatureAdded` events before it, the surprised conditions follow it.
- `TurnStarted(creature_id, round, active_index, economy)`: the turn of the entry at
  `active_index` opens; `round` is the (possibly incremented) round; `economy` is the creature's
  fresh budget (already reflecting the start-of-turn consequences that follow the event).
- `TurnEnded(creature_id)`: the open turn closes (end-of-turn ticks came before it).
- `EconomyChanged(creature_id, economy, reason)`: the combatant's budget becomes `economy`
  (spending an action, Dash, Disengage, a reaction).
- `CombatantWithdrew(creature_id, reason)`: the combatant fled or surrendered.
- `EncounterEnded(status, xp_total, xp_each, recipients)`: the fight is over with `status`;
  kill XP `xp_total` was split into `xp_each` for every id in `recipients` (the `XpGained`
  events follow). The encounter stays in state with its final status.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.encounter import Encounter, EncounterStatus, TurnEconomy, WithdrawReason


class _EncounterEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EncounterStarted(_EncounterEvent):
    type: Literal["encounter_started"] = "encounter_started"
    encounter: Encounter


class TurnStarted(_EncounterEvent):
    type: Literal["turn_started"] = "turn_started"
    creature_id: str
    round: int = Field(ge=1)
    active_index: int = Field(ge=0)
    economy: TurnEconomy


class TurnEnded(_EncounterEvent):
    type: Literal["turn_ended"] = "turn_ended"
    creature_id: str


class EconomyChanged(_EncounterEvent):
    type: Literal["economy_changed"] = "economy_changed"
    creature_id: str
    economy: TurnEconomy
    reason: str = ""


class CombatantWithdrew(_EncounterEvent):
    type: Literal["combatant_withdrew"] = "combatant_withdrew"
    creature_id: str
    reason: WithdrawReason


class EncounterEnded(_EncounterEvent):
    type: Literal["encounter_ended"] = "encounter_ended"
    status: EncounterStatus
    xp_total: int = Field(default=0, ge=0)
    xp_each: int = Field(default=0, ge=0)
    recipients: tuple[str, ...] = ()
