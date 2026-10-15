"""Quest lines of the public projection (M23.7): what the journal may show.

Owner rule: only DONE step texts leave the server. The text of a step that is not done yet is
the answer to "What now?" (M23.8) and never part of any snapshot. Every text passes `leaks`.
M23.9 `public_finale`: the finale question with both ending titles once the final region is
resolved (the card while nothing is chosen), then the chosen ending and its text.
Public API: `public_quests`, `public_leads`, `public_finale`.
"""

from aidm.models.protocol_views import (
    PublicFinale,
    PublicFinaleOption,
    PublicQuest,
    PublicRoute,
)
from aidm.models.quests import QuestKind, RoutePlan
from aidm.models.state import GameState
from aidm.models.world import Quest
from aidm.rules.finale import chosen_ending, finale_open
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


_FALLBACK_TITLE = {
    "force": "Defeat the master of {region}",
    "peace": "Another way past the master of {region}",
    "cunning": "Weaken the master of {region}",
}


def _route_plans(state: GameState, quest: Quest) -> tuple[dict[str, RoutePlan], str]:
    campaign = state.campaign
    if campaign is None or quest.kind is not QuestKind.MAIN:
        return {}, ""
    plan = campaign.plan
    act = next((a for a in plan.acts if main_quest_id(a.region) == quest.id), None)
    if act is None:
        return {}, ""
    return {r.id: r for r in main_quest(plan, act.index).routes}, act.region.name


def _route_title(route: RoutePlan, region: str, private: list[str]) -> str:
    title = _clean(route.title, private)
    return title or _FALLBACK_TITLE[route.kind.value].format(region=region)


def _routes(state: GameState, quest: Quest, private: list[str]) -> tuple[PublicRoute, ...]:
    plans, region = _route_plans(state, quest)
    out: list[PublicRoute] = []
    for progress in quest.routes:
        route = plans.get(progress.route_id)
        if route is None:
            continue
        out.append(
            PublicRoute(
                id=route.id,
                title=_route_title(route, region, private),
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


def public_finale(state: GameState) -> PublicFinale | None:
    campaign = state.campaign
    finale = campaign.plan.finale if campaign is not None else None
    chosen = chosen_ending(state)
    if finale is None or (finale_open(state) is None and chosen is None):
        return None
    return PublicFinale(
        question=finale.question,
        options=tuple(PublicFinaleOption(id=o.id, title=o.title) for o in finale.options),
        chosen=chosen.id if chosen is not None else None,
        ending=chosen.text if chosen is not None else "",
    )
