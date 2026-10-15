"""Quest lines of the public projection (M23.7): what the journal may show.

Owner rule: only DONE step texts leave the server. The text of a step that is not done yet is
the answer to "What now?" (M23.8) and never part of any snapshot. Every text passes `leaks`.
Public API: `public_quests`, `public_leads`.
"""

from aidm.models.protocol_views import PublicQuest, PublicRoute
from aidm.models.quests import QuestKind, RoutePlan
from aidm.models.state import GameState
from aidm.models.world import Quest
from aidm.rules.plan_ids import main_quest_id
from aidm.rules.quest_plan import main_quest
from aidm.session.public_feed import leaks, private_texts


def _private(state: GameState) -> list[str]:
    """The private texts plus the names of bosses the party has not reached yet."""
    world = state.world
    unmet = [
        n.name.lower()
        for n in world.npcs.values()
        if n.role == "boss" and n.node_id != world.current_node and n.node_id not in world.visited
    ]
    return [*private_texts(state), *unmet]


def _clean(text: str, private: list[str]) -> str:
    return "" if leaks(text, private) else text


def _done_texts(steps: tuple[object, ...], done: int, private: list[str]) -> tuple[str, ...]:
    texts = [getattr(step, "text", "") for step in steps[:done]]
    return tuple(t for t in (_clean(text, private) for text in texts) if t)


def _route_plans(state: GameState, quest: Quest) -> dict[str, RoutePlan]:
    campaign = state.campaign
    if campaign is None or quest.kind is not QuestKind.MAIN:
        return {}
    plan = campaign.plan
    act = next((a for a in plan.acts if main_quest_id(a.region) == quest.id), None)
    if act is None:
        return {}
    return {r.id: r for r in main_quest(plan, act.index).routes}


def _routes(state: GameState, quest: Quest, private: list[str]) -> tuple[PublicRoute, ...]:
    plans = _route_plans(state, quest)
    out: list[PublicRoute] = []
    for progress in quest.routes:
        route = plans.get(progress.route_id)
        if route is None:
            continue
        out.append(
            PublicRoute(
                id=route.id,
                title=_clean(route.title, private),
                kind=route.kind.value,
                steps_done=_done_texts(route.steps, progress.steps_done, private),
                done=progress.steps_done >= len(route.steps),
            )
        )
    return tuple(out)


def _public_quest(state: GameState, quest: Quest, goal: str, private: list[str]) -> PublicQuest:
    npc = state.world.npcs.get(quest.giver_npc_id or "")
    return PublicQuest(
        id=quest.id,
        title=quest.title,
        state=quest.state.value,
        kind=quest.kind.value,
        giver=npc.name if npc is not None else "",
        objective=_clean(goal, private),
        steps_done=_done_texts(quest.steps, quest.steps_done, private),
        routes=_routes(state, quest, private),
        log=tuple(t for t in (_clean(line, private) for line in quest.log) if t),
        closed_reason=quest.closed_reason.value if quest.closed_reason is not None else "",
    )


def public_quests(state: GameState) -> tuple[PublicQuest, ...]:
    """Quest lines with giver and objective (an offered quest was asked in person, so both are
    told), the done steps, the known routes of a main quest and the log. Text naming private
    things is left out."""
    private = _private(state)
    plan = {q.id: q.objective for q in state.campaign.plan.quests} if state.campaign else {}
    quests = sorted(state.world.quests.values(), key=lambda q: q.id)
    return tuple(
        _public_quest(state, q, q.objective or plan.get(q.id, ""), private) for q in quests
    )


def public_leads(state: GameState) -> tuple[str, ...]:
    private = _private(state)
    return tuple(t for t in (_clean(lead.text, private) for lead in state.world.leads) if t)
