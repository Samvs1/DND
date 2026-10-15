"""Plain-language lines for the quest events (M23.2): one set for the model, one for templates.

`QUEST_EVENT_LINES` join `aidm.dm.event_text` (authoritative, for the model);
`QUEST_TEMPLATE_LINES` join `aidm.dm.narration_templates` (for players when no model is
available). A step line names the quest and the step that was done (its log line); a route line
names the route the party just found. Only discovered routes are ever named. A hand-over line
says who handed what to whom (M23.3), the same for both. M23.4: the quest state lines live here
(taken on, left behind), the giver's ask (the model is told "<giver> asks the party:
<objective>" and to invent no other quest) and a new lead; a declined ask and a dropped lead are
bookkeeping (no line).
"""

from collections.abc import Callable
from typing import Any

from aidm.models.quest_events import (
    KeepsakeGiven,
    QuestAskDeclined,
    QuestAsked,
    QuestLeadAdded,
    QuestLeadRemoved,
    QuestStepDone,
    RouteDiscovered,
)
from aidm.models.state import GameState
from aidm.models.world import ClosedReason, QuestState
from aidm.models.world_events import QuestUpdated
from aidm.rules.plan_ids import main_quest_id
from aidm.rules.quest_plan import main_quest

_QUESTS = {
    QuestState.OFFERED: "A new task is offered: {title}.",
    QuestState.ACTIVE: "A task now lies before you: {title}.",
    QuestState.COMPLETED: "You have seen {title} through to the end.",
    QuestState.FAILED: "{title} has slipped beyond your reach.",
}
LEFT_BEHIND_STORY = "{title} is left behind, unfinished."


def _title(state: GameState, quest_id: str) -> str:
    quest = state.world.quests.get(quest_id)
    return quest.title if quest is not None else "a task"


def _route_title(state: GameState, quest_id: str, route_id: str) -> str:
    campaign = state.campaign
    if campaign is None:
        return "another way"
    plan = campaign.plan
    act = next((a for a in plan.acts if main_quest_id(a.region) == quest_id), None)
    route = main_quest(plan, act.index).route(route_id) if act is not None else None
    return route.title if route is not None else "another way"


def _step_fact(state: GameState, e: QuestStepDone) -> str:
    done = e.log_line or f"step {e.step + 1}"
    return f"Quest '{_title(state, e.quest_id)}': step done: {done}."


def _route_fact(state: GameState, e: RouteDiscovered) -> str:
    route = _route_title(state, e.quest_id, e.route_id)
    return f"Quest '{_title(state, e.quest_id)}': the party found a way: {route}."


def _step_story(state: GameState, e: QuestStepDone) -> str:
    done = e.log_line.rstrip(".") if e.log_line else "Part of it"
    return f"{done}: one more part of {_title(state, e.quest_id)} is done."


def _route_story(state: GameState, e: RouteDiscovered) -> str:
    route = _route_title(state, e.quest_id, e.route_id)
    return f"Another way opens before you: {route}."


def _given(state: GameState, e: KeepsakeGiven) -> str:
    hero = state.creatures.get(e.creature_id)
    npc = state.world.npcs.get(e.npc_id)
    held = [
        *(npc.keepsakes if npc is not None else []),
        *(hero.pc.keepsakes if hero and hero.pc else []),
    ]
    thing = next((k.name for k in held if k.id == e.keepsake_id), "something")
    who = hero.name if hero is not None else "Someone"
    return f"{who} hands the {thing} to {npc.name if npc is not None else 'them'}."


def _left(e: QuestUpdated) -> bool:
    return e.quest.closed_reason is ClosedReason.LEFT_BEHIND


def _updated_fact(state: GameState, e: QuestUpdated) -> str:
    quest = e.quest
    if _left(e):
        return f"Quest '{quest.title}' was left behind unfinished (no penalty)."
    if quest.state is QuestState.ACTIVE and quest.objective:
        return f"The party took on the quest '{quest.title}': {quest.objective}"
    return f"Quest '{quest.title}' is now {quest.state.value}."


def _updated_story(state: GameState, e: QuestUpdated) -> str:
    if _left(e):
        return LEFT_BEHIND_STORY.format(title=e.quest.title)
    return _QUESTS[e.quest.state].format(title=e.quest.title)


def _giver(state: GameState, e: QuestAsked) -> str:
    npc = state.world.npcs.get(e.ask.npc_id)
    return npc.name if npc is not None else "Someone"


def _asked_fact(state: GameState, e: QuestAsked) -> str:
    quest = state.world.quests.get(e.ask.quest_id)
    goal = (quest.objective or quest.title) if quest is not None else "a task"
    return (
        f"{_giver(state, e)} asks the party: {goal.rstrip('.')}. The players answer it"
        " themselves (Accept or Not now); invent no other quest."
    )


def _asked_story(state: GameState, e: QuestAsked) -> str:
    return f"{_giver(state, e)} asks for your help: {_title(state, e.ask.quest_id)}."


def _no_line(state: GameState, e: object) -> None:
    return None


QUEST_EVENT_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    QuestUpdated: _updated_fact,
    QuestAsked: _asked_fact,
    QuestLeadAdded: lambda s, e: f"A lead for the party: {e.lead.text}",
    QuestLeadRemoved: _no_line,
    QuestAskDeclined: _no_line,
    QuestStepDone: _step_fact,
    RouteDiscovered: _route_fact,
    KeepsakeGiven: _given,
}

QUEST_TEMPLATE_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    QuestUpdated: _updated_story,
    QuestAsked: _asked_story,
    QuestLeadAdded: lambda s, e: e.lead.text,
    QuestLeadRemoved: _no_line,
    QuestAskDeclined: _no_line,
    QuestStepDone: _step_story,
    RouteDiscovered: _route_story,
    KeepsakeGiven: _given,
}
