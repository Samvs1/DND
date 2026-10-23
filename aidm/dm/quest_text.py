"""Plain-language lines for the quest events (M23.2): one set for the model, one for templates.

`QUEST_EVENT_LINES` join `aidm.dm.event_text` (authoritative, for the model; facts only, since
they are public lines too); `QUEST_EVENT_NOTES` are the model-only instructions (M29.5c G36);
`QUEST_TEMPLATE_LINES` join `aidm.dm.narration_templates` (for players when no model is
available). A step line names the quest and the step that was done (its log line); a route line
names the route the party just found. Only discovered routes are ever named. A hand-over line
says who handed what to whom (M23.3), the same for both. M23.4: the quest state lines live here
(taken on, left behind), the giver's ask (the model is told "<giver> asks the party:
<objective>" and to invent no other quest) and a new lead; a declined ask and a dropped lead are
bookkeeping (no line). M23.5 favours: asked ("asks the party a favour"), taken on, done ("they are
grateful", never a reward) and let go; an offered favour has no line of its own (the ask says it).
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
from aidm.models.quests import QuestKind, QuestStep, RoutePlan, StepKind
from aidm.models.state import GameState
from aidm.models.world import ClosedReason, Quest, QuestState
from aidm.models.world_events import QuestUpdated
from aidm.rules.plan_ids import main_quest_id
from aidm.rules.quest_plan import main_quest
from aidm.rules.secrets import item_key

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


def _route(state: GameState, quest_id: str, route_id: str) -> RoutePlan | None:
    campaign = state.campaign
    if campaign is None:
        return None
    plan = campaign.plan
    act = next((a for a in plan.acts if main_quest_id(a.region) == quest_id), None)
    return main_quest(plan, act.index).route(route_id) if act is not None else None


def _route_title(state: GameState, quest_id: str, route_id: str) -> str:
    route = _route(state, quest_id, route_id)
    return route.title if route is not None else "another way"


def _step(state: GameState, e: QuestStepDone) -> QuestStep | None:
    if e.route_id is not None:
        route = _route(state, e.quest_id, e.route_id)
        steps = route.steps if route is not None else ()
    else:
        quest = state.world.quests.get(e.quest_id)
        steps = quest.steps if quest is not None else ()
    return steps[e.step] if 0 <= e.step < len(steps) else None


def _holder(state: GameState, item: str) -> str | None:
    wanted = item_key(item)
    for c in state.creatures.values():
        if c.pc is None or c.dead:
            continue
        names = [k.name for k in c.pc.keepsakes] + [row.item for row in c.pc.inventory]
        if any(item_key(n) == wanted for n in names):
            return c.name
    return None


def _step_fact(state: GameState, e: QuestStepDone) -> str:
    """M29.5b G20: a step is met by what the state already records (an item found before the
    quest was taken counts at once), so the model is told what met it and to tell no new deed."""
    done = (e.log_line or f"step {e.step + 1}").rstrip(".")
    step = _step(state, e)
    held = None
    if step is not None and step.kind is StepKind.OBTAIN and step.item:
        who = _holder(state, step.item)
        held = f"{who} already carries the {step.item}" if who is not None else None
    why = held or "met by what the party has already done"
    return f"Quest '{_title(state, e.quest_id)}': step done: {done} ({why})."


STEP_NOTE = (
    "Describe no new deed for a quest step marked done: what the party did or carries met it."
)


def _route_fact(state: GameState, e: RouteDiscovered) -> str:
    route = _route_title(state, e.quest_id, e.route_id)
    return f"Quest '{_title(state, e.quest_id)}': a way the party knows of: {route}."


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


def _favour_fact(state: GameState, quest: Quest) -> str:
    giver = _npc(state, quest.giver_npc_id)
    if quest.closed_reason is ClosedReason.WITHDRAWN:
        return f"The favour '{quest.title}' for {giver} was let go (no penalty)."
    if quest.state is QuestState.COMPLETED:
        return f"The favour '{quest.title}' for {giver} is done: they are grateful (no reward)."
    if quest.state is QuestState.ACTIVE:
        return f"The party agreed to do {giver} a favour: {quest.objective or quest.title}"
    return f"Favour '{quest.title}' is now {quest.state.value}."


def _favour_story(state: GameState, quest: Quest) -> str | None:
    giver = _npc(state, quest.giver_npc_id)
    if quest.closed_reason is ClosedReason.WITHDRAWN:
        return f"You let {giver}'s favour go."
    if quest.state is QuestState.COMPLETED:
        return f"You did {giver} a favour: {quest.title}. They will remember it."
    if quest.state is QuestState.ACTIVE:
        return f"You agree to do {giver} a favour: {quest.title}."
    return None  # offered: the ask line says it


def _updated_fact(state: GameState, e: QuestUpdated) -> str | None:
    quest = e.quest
    if _left(e):
        return f"Quest '{quest.title}' was left behind unfinished (no penalty)."
    if quest.state is QuestState.OFFERED:
        return None  # the ask line says who asks
    if quest.kind is QuestKind.FAVOUR:
        return _favour_fact(state, quest)
    if quest.state is QuestState.ACTIVE and quest.objective:
        return f"The party took on the quest '{quest.title}': {quest.objective}"
    return f"Quest '{quest.title}' is now {quest.state.value}."


def _updated_story(state: GameState, e: QuestUpdated) -> str | None:
    if _left(e):
        return LEFT_BEHIND_STORY.format(title=e.quest.title)
    if e.quest.kind is QuestKind.FAVOUR:
        return _favour_story(state, e.quest)
    return _QUESTS[e.quest.state].format(title=e.quest.title)


def _npc(state: GameState, npc_id: str | None) -> str:
    npc = state.world.npcs.get(npc_id or "")
    return npc.name if npc is not None else "Someone"


def _giver(state: GameState, e: QuestAsked) -> str:
    return _npc(state, e.ask.npc_id)


def _is_favour(state: GameState, quest_id: str) -> bool:
    quest = state.world.quests.get(quest_id)
    return quest is not None and quest.kind is QuestKind.FAVOUR


def _asked_fact(state: GameState, e: QuestAsked) -> str:
    quest = state.world.quests.get(e.ask.quest_id)
    goal = (quest.objective or quest.title) if quest is not None else "a task"
    asks = "asks the party a favour: " if _is_favour(state, e.ask.quest_id) else "asks the party: "
    return (
        f"{_giver(state, e)} {asks}{goal.rstrip('.')}. The players answer it"
        " themselves (Accept or Not now); invent no other quest."
    )


def _asked_story(state: GameState, e: QuestAsked) -> str:
    title = _title(state, e.ask.quest_id)
    if _is_favour(state, e.ask.quest_id):
        return f"{_giver(state, e)} asks a favour of you: {title}."
    return f"{_giver(state, e)} asks for help: {title}."


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

# M29.5c G36: model-only instructions, kept out of the lines players can see
QUEST_EVENT_NOTES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    QuestStepDone: lambda s, e: STEP_NOTE,
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
