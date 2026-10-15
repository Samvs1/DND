"""Read the quests of a campaign plan, deriving what an old plan lacks (M23, GOAL "Old saves").

Pure. The ONE place a plan's quest steps and main quests are read: every reader goes through
it, so a plan written before M23 (no steps, no stored routes, no finale) reads like a new one.

- A side quest without steps gets `[free(objective), meet(giver)]`.
- The main quest of an act: id `main-<region id>` (`plan_ids.main_quest_id`), title = act title,
  objective = act goal. Its Force route is ALWAYS built here (visit every spoke, then defeat the
  boss; SPEC 9: defeat is never removed). The stored Peace / Cunning routes follow; a boss with
  an ally path and no stored Peace route gets a Peace route of one `free` step from the ally path.

Public API: `short_text(text, limit)`, `quest_steps(plan, quest)`, `force_route(region)`,
`main_quest(plan, act_index)`, `main_quests(plan)`, `side_world_quest(plan, quest)` and
`main_world_quest(plan, act_index)` (the `World.quests` entries; Force is known from the start).
"""

from aidm.models.campaign import Act, CampaignPlan, QuestPlan, RegionPlan
from aidm.models.quests import (
    FORCE_ROUTE_ID,
    MAX_STEP_TEXT,
    MainQuest,
    QuestKind,
    QuestStep,
    RouteKind,
    RoutePlan,
    StepKind,
)
from aidm.models.world import Quest, QuestState, RouteProgress
from aidm.rules.plan_ids import boss_npc_id, main_quest_id

PEACE_ROUTE_ID = "peace"
ELLIPSIS = "..."


def short_text(text: str, limit: int = MAX_STEP_TEXT) -> str:
    """`text` cut to `limit` characters at a word boundary (an ellipsis marks the cut)."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - len(ELLIPSIS)]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + ELLIPSIS


def _npc_name(plan: CampaignPlan, npc_id: str) -> str:
    return next((n.name for n in plan.npcs if n.id == npc_id), npc_id)


def quest_steps(plan: CampaignPlan, quest: QuestPlan) -> tuple[QuestStep, ...]:
    if quest.steps:
        return quest.steps
    giver = _npc_name(plan, quest.giver_npc_id)
    return (
        QuestStep(kind=StepKind.FREE, text=short_text(quest.objective)),
        QuestStep(kind=StepKind.MEET, text=f"Return to {giver}", npc=quest.giver_npc_id),
    )


def force_route(region: RegionPlan) -> RoutePlan:
    boss = region.boss
    explore = QuestStep(
        kind=StepKind.VISIT,
        text=short_text(f"Explore every corner of {region.name}"),
        nodes=tuple(s.id for s in region.spokes),
    )
    defeat = QuestStep(
        kind=StepKind.DEFEAT,
        text=short_text(f"Defeat {boss.name} at {region.gateway.name}"),
        npc=boss_npc_id(region),
    )
    return RoutePlan(
        id=FORCE_ROUTE_ID,
        kind=RouteKind.FORCE,
        title=short_text(f"Defeat {boss.name}", 60),
        steps=(explore, defeat),
    )


def _legacy_peace(region: RegionPlan) -> RoutePlan | None:
    boss = region.boss
    if boss.ally_path is None:
        return None
    return RoutePlan(
        id=PEACE_ROUTE_ID,
        kind=RouteKind.PEACE,
        title=short_text(f"Win {boss.name} over", 60),
        steps=(QuestStep(kind=StepKind.FREE, text=short_text(boss.ally_path)),),
    )


def _routes(act: Act) -> tuple[RoutePlan, ...]:
    stored = act.main.routes if act.main is not None else ()
    routes = [force_route(act.region)]
    peace = next((r for r in stored if r.kind is RouteKind.PEACE), None)
    legacy = _legacy_peace(act.region) if peace is None else None
    routes += [peace] if peace is not None else ([legacy] if legacy is not None else [])
    routes += [r for r in stored if r.kind is RouteKind.CUNNING]
    return tuple(routes)


def main_quest(plan: CampaignPlan, act_index: int) -> MainQuest:
    act = plan.acts[act_index - 1]
    return MainQuest(
        id=main_quest_id(act.region),
        act=act.index,
        title=act.title,
        objective=act.goal,
        routes=_routes(act),
    )


def main_quests(plan: CampaignPlan) -> tuple[MainQuest, ...]:
    return tuple(main_quest(plan, a.index) for a in plan.acts)


def side_world_quest(plan: CampaignPlan, quest: QuestPlan) -> Quest:
    return Quest(
        id=quest.id,
        title=quest.title,
        state=QuestState.OFFERED,
        giver_npc_id=quest.giver_npc_id,
        against_npc_id=quest.against_npc_id,
        kind=QuestKind.SIDE,
        objective=quest.objective,
        steps=quest_steps(plan, quest),
    )


def main_world_quest(plan: CampaignPlan, act_index: int) -> Quest:
    main = main_quest(plan, act_index)
    return Quest(
        id=main.id,
        title=main.title,
        state=QuestState.ACTIVE,
        kind=QuestKind.MAIN,
        objective=main.objective,
        routes=(RouteProgress(route_id=FORCE_ROUTE_ID),),
    )
