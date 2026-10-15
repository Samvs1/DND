"""Quest events (M23; part of `aidm.models.world_events.WorldEvents`, same design rules).

Applied by `aidm.session.quest_apply`. Payloads are resolved: the engine decided the step is done
or the route is found before the event exists; the reducer only records it.

Public API:
- `QuestStepDone(quest_id, route_id, step, log_line)`: step `step` (0-based, the next one) of the
  quest's own steps (`route_id` None) or of one of its known routes is done; a non-empty
  `log_line` joins the quest log.
- `RouteDiscovered(quest_id, route_id)`: the party now knows this route of the main quest.
- `QuestLeadAdded(lead)`: a journal lead toward a side quest's giver.
- `KeepsakeGiven(creature_id, keepsake_id, npc_id)`: the hero hands a keepsake to an NPC; it
  leaves the hero and joins `WorldNpc.keepsakes`.
- `QuestEvents`: the union of these classes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.quests import MAX_STEPS
from aidm.models.world import QuestLead


class _QuestEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class QuestStepDone(_QuestEvent):
    type: Literal["quest_step_done"] = "quest_step_done"
    quest_id: str = Field(min_length=1)
    route_id: str | None = None
    step: int = Field(ge=0, lt=MAX_STEPS)
    log_line: str = Field(default="", max_length=160)


class RouteDiscovered(_QuestEvent):
    type: Literal["route_discovered"] = "route_discovered"
    quest_id: str = Field(min_length=1)
    route_id: str = Field(min_length=1)


class QuestLeadAdded(_QuestEvent):
    type: Literal["quest_lead_added"] = "quest_lead_added"
    lead: QuestLead


class KeepsakeGiven(_QuestEvent):
    type: Literal["keepsake_given"] = "keepsake_given"
    creature_id: str = Field(min_length=1)
    keepsake_id: str = Field(min_length=1)
    npc_id: str = Field(min_length=1)


QuestEvents = QuestStepDone | RouteDiscovered | QuestLeadAdded | KeepsakeGiven
