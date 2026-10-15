"""Free steps: the one quest move the AI may make (M23.5, GOAL "Lifecycle"). Pure.

Plan quests (main and side) and favours are engine-owned: every typed step is checked by
`aidm.rules.quest_steps` after each batch. A `free` step ("calm the shrine's ghost") cannot be
checked, so the model proposes it through `update_quest` and the engine records it here: only the
CURRENT step of an ACTIVE quest, only when that step is `free`. For a main quest the step belongs
to one of its KNOWN routes (the route is named, or the only known route whose current step is
free); naming an undiscovered route whose first step is free discovers it (doing a step of a
route makes it known, GOAL "Kinds of quest"), so an old plan's one-step Peace route can finish.
The settle that follows completes the quest (or the route) when it was the last step.
Everything else is a `FreeStepRefused` whose message tells the model what to do instead.

Public API: `ENGINE_STEPS`, `FreeStepRefused`, `free_step_events(state, quest_id, route_id)
-> list[AnyEvent]`.
"""

from aidm.models.events import AnyEvent
from aidm.models.quest_events import QuestStepDone, RouteDiscovered
from aidm.models.quests import QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState, RouteProgress
from aidm.rules.plan_ids import main_quest_id
from aidm.rules.quest_plan import main_quest

ENGINE_STEPS = "quest steps are checked by the engine; only a free step can be marked done"


class FreeStepRefused(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _active(state: GameState, quest_id: str) -> Quest:
    quest = state.world.quests.get(quest_id)
    if quest is None:
        raise FreeStepRefused(
            f"unknown quest {quest_id!r}; quests exist only as listed (an NPC who wants help"
            " uses offer_favour)"
        )
    if quest.state is QuestState.OFFERED:
        raise FreeStepRefused(f"{quest.title!r} is not accepted yet; the players answer the card")
    if quest.state is not QuestState.ACTIVE:
        raise FreeStepRefused(f"{quest.title!r} is already {quest.state.value}")
    return quest


def _current(steps: tuple[QuestStep, ...], done: int) -> QuestStep | None:
    return steps[done] if done < len(steps) else None


def _free_route(state: GameState, quest: Quest, route_id: str | None) -> list[AnyEvent]:
    campaign = state.campaign
    act = None
    if campaign is not None:
        acts = campaign.plan.acts
        act = next((a for a in acts if main_quest_id(a.region) == quest.id), None)
    if campaign is None or act is None:
        raise FreeStepRefused(ENGINE_STEPS)
    routes = main_quest(campaign.plan, act.index).routes
    open_free: list[tuple[str, int, QuestStep]] = []
    found: list[AnyEvent] = []
    for route in routes:
        progress = quest.route(route.id)
        if progress is None and route.id == route_id:  # doing a step discovers its route
            progress = RouteProgress(route_id=route.id)
            found = [RouteDiscovered(quest_id=quest.id, route_id=route.id)]
        step = _current(route.steps, progress.steps_done) if progress is not None else None
        if progress is not None and step is not None and step.kind is StepKind.FREE:
            open_free.append((route.id, progress.steps_done, step))
    chosen = [c for c in open_free if route_id is None or c[0] == route_id]
    if len(chosen) != 1:
        raise FreeStepRefused(
            ENGINE_STEPS if not chosen else "name the route_id of the way the party followed"
        )
    rid, index, step = chosen[0]
    done = QuestStepDone(quest_id=quest.id, route_id=rid, step=index, log_line=step.text)
    return [*found, done]


def free_step_events(state: GameState, quest_id: str, route_id: str | None) -> list[AnyEvent]:
    quest = _active(state, quest_id)
    if quest.kind is QuestKind.MAIN:
        return _free_route(state, quest, route_id)
    step = _current(quest.steps, quest.steps_done)
    if step is None or step.kind is not StepKind.FREE:
        raise FreeStepRefused(ENGINE_STEPS)
    return [QuestStepDone(quest_id=quest.id, step=quest.steps_done, log_line=step.text)]
