"""Plain-language lines for the quest events (M23.2): one set for the model, one for templates.

`QUEST_EVENT_LINES` join `aidm.dm.event_text` (authoritative, for the model);
`QUEST_TEMPLATE_LINES` join `aidm.dm.narration_templates` (for players when no model is
available). A step line names the quest and the step that was done (its log line); a route line
names the route the party just found. Only discovered routes are ever named. A hand-over line
says who handed what to whom (M23.3), the same for both.
"""

from collections.abc import Callable
from typing import Any

from aidm.models.quest_events import KeepsakeGiven, QuestStepDone, RouteDiscovered
from aidm.models.state import GameState
from aidm.rules.plan_ids import main_quest_id
from aidm.rules.quest_plan import main_quest


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


QUEST_EVENT_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    QuestStepDone: _step_fact,
    RouteDiscovered: _route_fact,
    KeepsakeGiven: _given,
}

QUEST_TEMPLATE_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    QuestStepDone: _step_story,
    RouteDiscovered: _route_story,
    KeepsakeGiven: _given,
}
