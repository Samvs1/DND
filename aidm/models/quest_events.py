"""Quest events (M23; part of `aidm.models.world_events.WorldEvents`, same design rules).

Applied by `aidm.session.quest_apply`. Payloads are resolved: the engine decided the step is done
or the route is found before the event exists; the reducer only records it.

Public API:
- `QuestStepDone(quest_id, route_id, step, log_line)`: step `step` (0-based, the next one) of the
  quest's own steps (`route_id` None) or of one of its known routes is done; a non-empty
  `log_line` joins the quest log.
- `RouteDiscovered(quest_id, route_id)`: the party now knows this route of the main quest.
- `QuestLeadAdded(lead)`: a journal lead toward a side quest's giver (a `QuestUpdated` of that
  quest removes it, the quest is known then).
- `QuestLeadRemoved(quest_id)`: a lead of a region the party left (M23.4).
- `QuestAsked(ask)`: the giver asks the party (M23.4): the Accept / Not now card is open.
- `QuestAskDeclined(quest_id)`: "Not now": the card closes, the quest stays offered.
- `KeepsakeGiven(creature_id, keepsake_id, npc_id)`: the hero hands a keepsake to an NPC; it
  leaves the hero and joins `WorldNpc.keepsakes`.
- `KeepsakeTaken(creature_id, keepsake_id, npc_id)` (M29.7a R18): the hero lifted a keepsake
  the NPC holds (`aidm.rules.lifting`); it leaves `WorldNpc.keepsakes` and joins the hero.
- `LoreLearned(creature_id, item, tag)` (M29.9b T13): the hero took up or read a clue keepsake
  that teaches `tag`; `World.learned[tag]` records the seq (a learn step counts it while its
  quest is active, `aidm.rules.quest_steps`).
- `QuestEvents`: the union of these classes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.quests import MAX_STEPS
from aidm.models.world import QuestAsk, QuestLead


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


class QuestLeadRemoved(_QuestEvent):
    type: Literal["quest_lead_removed"] = "quest_lead_removed"
    quest_id: str = Field(min_length=1)


class QuestAsked(_QuestEvent):
    type: Literal["quest_asked"] = "quest_asked"
    ask: QuestAsk


class QuestAskDeclined(_QuestEvent):
    type: Literal["quest_ask_declined"] = "quest_ask_declined"
    quest_id: str = Field(min_length=1)


class KeepsakeGiven(_QuestEvent):
    type: Literal["keepsake_given"] = "keepsake_given"
    creature_id: str = Field(min_length=1)
    keepsake_id: str = Field(min_length=1)
    npc_id: str = Field(min_length=1)


class KeepsakeTaken(_QuestEvent):
    type: Literal["keepsake_taken"] = "keepsake_taken"
    creature_id: str = Field(min_length=1)
    keepsake_id: str = Field(min_length=1)
    npc_id: str = Field(min_length=1)


class LoreLearned(_QuestEvent):
    type: Literal["lore_learned"] = "lore_learned"
    creature_id: str = Field(min_length=1)
    item: str = Field(min_length=1)
    tag: str = Field(min_length=1)


QuestEvents = (
    QuestStepDone
    | RouteDiscovered
    | QuestLeadAdded
    | QuestLeadRemoved
    | QuestAsked
    | QuestAskDeclined
    | KeepsakeGiven
    | KeepsakeTaken
    | LoreLearned
)
