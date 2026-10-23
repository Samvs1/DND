"""Reducer part for the quest events (M23; called from `aidm.session.world_apply`).

Same semantics as the reducer: plain assignment of resolved values, `ReducerError` for an event
that does not fit the state (an engine bug). Steps are sequential: a `QuestStepDone` must name
the next step. Quests are frozen models, so a change replaces the quest.

M23.4: a `QuestUpdated` (applied through `quest_updated`) removes that quest's lead (the quest
is known now) and closes the giver's open question once the quest is no longer offered;
`QuestAsked` opens the question (one at a time), `QuestAskDeclined` closes it, a move clears it
(`world_apply`).

Public API: `QuestEvent` (the union), `QUEST_EVENT_TYPES`, `apply_quest_event(state, event)`,
`quest_updated(state, quest)`.
"""

from typing import assert_never

from aidm.models.quest_events import (
    KeepsakeGiven,
    KeepsakeTaken,
    QuestAskDeclined,
    QuestAsked,
    QuestLeadAdded,
    QuestLeadRemoved,
    QuestStepDone,
    RouteDiscovered,
)
from aidm.models.state import GameState
from aidm.models.world import MAX_QUEST_LOG, Quest, QuestAsk, QuestState, RouteProgress
from aidm.session.reducer_errors import ReducerError

type QuestEvent = (
    QuestStepDone
    | RouteDiscovered
    | QuestLeadAdded
    | QuestLeadRemoved
    | QuestAsked
    | QuestAskDeclined
    | KeepsakeGiven
    | KeepsakeTaken
)

QUEST_EVENT_TYPES = (
    QuestStepDone,
    RouteDiscovered,
    QuestLeadAdded,
    QuestLeadRemoved,
    QuestAsked,
    QuestAskDeclined,
    KeepsakeGiven,
    KeepsakeTaken,
)


def _quest(state: GameState, quest_id: str) -> Quest:
    quest = state.world.quests.get(quest_id)
    if quest is None:
        raise ReducerError(f"unknown quest {quest_id!r}")
    return quest


def _logged(quest: Quest, line: str) -> tuple[str, ...]:
    return (*quest.log, line)[-MAX_QUEST_LOG:] if line else quest.log


def _route_step(quest: Quest, event: QuestStepDone, route_id: str) -> Quest:
    progress = quest.route(route_id)
    if progress is None:
        raise ReducerError(f"quest {quest.id!r}: route {route_id!r} is not known")
    if event.step != progress.steps_done:
        raise ReducerError(
            f"quest {quest.id!r}: route {route_id!r} is at step {progress.steps_done}"
        )
    done = RouteProgress(route_id=route_id, steps_done=progress.steps_done + 1)
    routes = tuple(done if r.route_id == route_id else r for r in quest.routes)
    return quest.model_copy(update={"routes": routes, "log": _logged(quest, event.log_line)})


def _step_done(quest: Quest, event: QuestStepDone) -> Quest:
    if event.route_id is not None:
        return _route_step(quest, event, event.route_id)
    if event.step != quest.steps_done or event.step >= len(quest.steps):
        raise ReducerError(f"quest {quest.id!r} is at step {quest.steps_done}, not {event.step}")
    update = {"steps_done": quest.steps_done + 1, "log": _logged(quest, event.log_line)}
    return quest.model_copy(update=update)


def _discovered(quest: Quest, route_id: str) -> Quest:
    if quest.route(route_id) is not None:
        raise ReducerError(f"quest {quest.id!r}: route {route_id!r} is already known")
    return quest.model_copy(update={"routes": (*quest.routes, RouteProgress(route_id=route_id))})


def _given(state: GameState, event: KeepsakeGiven) -> None:
    creature = state.creatures.get(event.creature_id)
    npc = state.world.npcs.get(event.npc_id)
    if creature is None or creature.pc is None or npc is None:
        raise ReducerError(f"no hero {event.creature_id!r} or npc {event.npc_id!r} to give to")
    held = creature.pc.keepsakes
    keepsake = next((k for k in held if k.id == event.keepsake_id), None)
    if keepsake is None:
        raise ReducerError(f"hero {event.creature_id!r} has no keepsake {event.keepsake_id!r}")
    held.remove(keepsake)
    npc.keepsakes.append(keepsake.model_copy())


def _taken(state: GameState, event: KeepsakeTaken) -> None:
    creature = state.creatures.get(event.creature_id)
    npc = state.world.npcs.get(event.npc_id)
    if creature is None or creature.pc is None or npc is None:
        raise ReducerError(f"no hero {event.creature_id!r} or npc {event.npc_id!r} to take from")
    keepsake = next((k for k in npc.keepsakes if k.id == event.keepsake_id), None)
    if keepsake is None:
        raise ReducerError(f"npc {event.npc_id!r} holds no keepsake {event.keepsake_id!r}")
    npc.keepsakes.remove(keepsake)
    creature.pc.keepsakes.append(keepsake.model_copy())


def quest_updated(state: GameState, quest: Quest) -> None:
    world = state.world
    world.quests[quest.id] = quest
    world.leads = [lead for lead in world.leads if lead.quest_id != quest.id]
    ask = world.quest_ask
    if ask is not None and ask.quest_id == quest.id and quest.state is not QuestState.OFFERED:
        world.quest_ask = None


def _asked(state: GameState, ask: QuestAsk) -> None:
    world = state.world
    quest = world.quests.get(ask.quest_id)
    if world.quest_ask is not None:
        raise ReducerError(f"quest {world.quest_ask.quest_id!r} is already being asked")
    if quest is None or quest.state is not QuestState.OFFERED:
        raise ReducerError(f"quest {ask.quest_id!r} is not offered")
    world.quest_ask = ask


def _declined(state: GameState, quest_id: str) -> None:
    world = state.world
    if world.quest_ask is None or world.quest_ask.quest_id != quest_id:
        raise ReducerError(f"quest {quest_id!r} is not being asked")
    world.quest_ask = None


def _lead_removed(state: GameState, quest_id: str) -> None:
    world = state.world
    if not any(lead.quest_id == quest_id for lead in world.leads):
        raise ReducerError(f"quest {quest_id!r} has no lead")
    world.leads = [lead for lead in world.leads if lead.quest_id != quest_id]


def apply_quest_event(state: GameState, event: QuestEvent) -> None:
    world = state.world
    match event:
        case QuestStepDone(quest_id=quest_id):
            world.quests[quest_id] = _step_done(_quest(state, quest_id), event)
        case RouteDiscovered(quest_id=quest_id, route_id=route_id):
            world.quests[quest_id] = _discovered(_quest(state, quest_id), route_id)
        case QuestLeadAdded(lead=lead):
            if any(known.quest_id == lead.quest_id for known in world.leads):
                raise ReducerError(f"quest {lead.quest_id!r} already has a lead")
            world.leads.append(lead)
        case QuestLeadRemoved(quest_id=quest_id):
            _lead_removed(state, quest_id)
        case QuestAsked(ask=ask):
            _asked(state, ask)
        case QuestAskDeclined(quest_id=quest_id):
            _declined(state, quest_id)
        case KeepsakeGiven():
            _given(state, event)
        case KeepsakeTaken():
            _taken(state, event)
        case _:
            assert_never(event)
