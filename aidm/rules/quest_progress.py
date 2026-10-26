"""The engine moves quests (M23.2, GOAL "Steps", "Kinds of quest"). Pure: returns events.

One call is ONE pass over the current state; the session repeats passes after every mechanics
batch until nothing moves (`aidm.session.quest_flow`), because each pass only acts on what the
state already records (a step event must be applied before the quest can complete over it).
A pass, in order:
1. Backfill: every act up to the current one (`current_act`) has its main quest
   (`quest_plan.main_world_quest`: active, Force known); fresh installs, act changes and old
   saves get it here. The current act's quest items missing from the world are placed
   (`quest_items.quest_item_events`, idempotent: old saves get theirs here, M23.3).
2. Each ACTIVE main quest: route steps met by the state are recorded (`QuestStepDone` with the
   step text as log line); an unknown route is discovered first (`RouteDiscovered`) when one of
   its steps is met or its hint NPC can be met (present, alive, not hostile). Once nothing moves
   and the act region is resolved, the quest completes with a log line saying how (defeat or
   alliance). A finished Peace route gives the boss the deeds that reach ALLY, so the EXISTING
   alliance resolution (`progression.region_resolution_events`) resolves the region; while the
   master's encounter offer waits, the deeds wait too unless the last step was the party's own
   hand-over (M29.7c R14: the party answers, and with the route done a parley surely holds,
   `offer_answer`); a finished
   Cunning route is read by the boss offer through `route_effects` (no event of its own).
3. Each ACTIVE side quest or favour with steps: first (M41.4, round 7 Z14) one whose steps do
   not end with its giver gets the report to them (`quest_targets.report_step_due`,
   `QuestStepAdded`: the giver pays, so the task is handed in where it was given); newly met
   steps are recorded; when every step
   is recorded the quest completes with `quest_deed_events` + `quest_reward_events` (once: only
   an active quest completes, and the payout refuses a quest already completed).
Several quests can finish in one pass, all read from the same state (M35.1, round-6 Y1: the
second payout overwrote the first): the pass's gold, XP and item totals are chained
(`rules.running_totals.chain_totals`), and a quest whose deeds would touch an NPC another
completion or Peace route of this pass already moved waits for the next pass (an
`AttitudeChanged` carries absolute values and no change to chain).
Offered quests never move. A quest without steps (made up by the model) never moves by itself.

Public API: `current_act(state) -> int | None`, `quest_progress_events(state, tiers, catalogue)
-> list[AnyEvent]`, `route_effects(state, region) -> frozenset[RouteEffect]`,
`peace_ready(state, region) -> bool` (every step of the region's Peace route is done).
"""

from aidm.data.dm_tiers import DmTiers
from aidm.data.item_catalogue import CatalogueItem
from aidm.data.registry import Registry
from aidm.models.campaign import Act, CampaignPlan, RegionPlan
from aidm.models.campaign_state import RegionResolution
from aidm.models.events import AnyEvent
from aidm.models.quest_events import QuestStepAdded, QuestStepDone, RouteDiscovered
from aidm.models.quests import QuestKind, RouteEffect, RouteKind, RoutePlan, StepKind
from aidm.models.state import GameState
from aidm.models.world import MAX_QUEST_LOG, Quest, QuestState
from aidm.models.world_events import AttitudeChanged, QuestUpdated
from aidm.rules.plan_ids import boss_npc_id, main_quest_id
from aidm.rules.progression import region_of
from aidm.rules.quest_items import quest_item_events
from aidm.rules.quest_plan import main_quest, main_world_quest
from aidm.rules.quest_rewards import quest_reward_events
from aidm.rules.quest_steps import npc_meetable, steps_met
from aidm.rules.quest_targets import report_step_due
from aidm.rules.running_totals import chain_totals
from aidm.rules.social import ALLY_BAR, attitude_score, deed_attitude_events
from aidm.rules.social_deeds import quest_deed_events

ANSWERING_STEPS = frozenset({StepKind.DELIVER})
RESOLVED_LINES = {
    RegionResolution.DEFEAT: "{boss} was defeated.",
    RegionResolution.ALLIANCE: "{boss} was won over.",
}


def current_act(state: GameState) -> int | None:
    """The act the party is in: the region of its place, else the first unresolved act."""
    campaign = state.campaign
    if campaign is None:
        return None
    acts = campaign.plan.acts
    here = region_of(state, state.world.current_node)
    if here is not None:
        return next(a.index for a in acts if a.region.id == here.id)
    open_acts = [a.index for a in acts if a.region.id not in campaign.resolved]
    return open_acts[0] if open_acts else acts[-1].index


def _backfill(state: GameState, plan: CampaignPlan) -> list[AnyEvent]:
    last = current_act(state) or 0
    events: list[AnyEvent] = [
        QuestUpdated(quest=main_world_quest(plan, act.index))
        for act in plan.acts[:last]
        if main_quest_id(act.region) not in state.world.quests
    ]
    return [*events, *(quest_item_events(state, plan, last) if last else [])]


def _route_steps(state: GameState, quest: Quest, route: RoutePlan) -> list[AnyEvent]:
    progress = quest.route(route.id)
    done = progress.steps_done if progress is not None else 0
    met = steps_met(state, route.steps, done, quest.id)
    events: list[AnyEvent] = []
    if progress is None:
        if met == done and not npc_meetable(state, route.hint_npc_id):
            return []
        events.append(RouteDiscovered(quest_id=quest.id, route_id=route.id))
    events += [
        QuestStepDone(quest_id=quest.id, route_id=route.id, step=i, log_line=route.steps[i].text)
        for i in range(done, met)
    ]
    return events


def _peace_deeds(
    state: GameState, quest: Quest, route: RoutePlan, region: RegionPlan
) -> list[AnyEvent]:
    progress = quest.route(route.id)
    if route.kind is not RouteKind.PEACE or progress is None:
        return []
    if progress.steps_done < len(route.steps):
        return []
    if route.steps[-1].kind not in ANSWERING_STEPS and _offer_waits(state, region):
        return []
    boss = state.world.npcs.get(boss_npc_id(region))
    if boss is None or boss.dead or boss.hostile:
        return []
    needed = ALLY_BAR - attitude_score(boss)
    return deed_attitude_events(boss, needed, f"route {route.id} done") if needed > 0 else []


def _offer_waits(state: GameState, region: RegionPlan) -> bool:
    """The master's encounter offer is waiting for the party's answer (M29.7c R14: a Peace route
    finished by arriving never answers it; the party does, and a parley then surely holds. A
    hand-over to the master, `ANSWERING_STEPS`, is the party's own answer)."""
    campaign = state.campaign
    offer = campaign.offer if campaign is not None else None
    return offer is not None and offer.boss_npc_id == boss_npc_id(region)


def peace_ready(state: GameState, region: RegionPlan) -> bool:
    """Every step of `region`'s Peace route is done (the master is ready to be won over)."""
    campaign = state.campaign
    quest = state.world.quests.get(main_quest_id(region))
    act = (
        next((a for a in campaign.plan.acts if a.region.id == region.id), None)
        if campaign
        else None
    )
    if campaign is None or quest is None or act is None:
        return False
    for route in main_quest(campaign.plan, act.index).routes:
        progress = quest.route(route.id)
        if route.kind is RouteKind.PEACE and progress is not None:
            return progress.steps_done >= len(route.steps)
    return False


def _completed(state: GameState, quest: Quest, act: Act) -> Quest:
    campaign = state.campaign
    how = campaign.resolved[act.region.id] if campaign is not None else RegionResolution.DEFEAT
    line = RESOLVED_LINES[how].format(boss=act.region.boss.name)
    log = (*quest.log, line)[-MAX_QUEST_LOG:]
    return quest.model_copy(update={"state": QuestState.COMPLETED, "log": log})


def _main_events(state: GameState, plan: CampaignPlan, act: Act, quest: Quest) -> list[AnyEvent]:
    routes = main_quest(plan, act.index).routes
    steps = [e for route in routes for e in _route_steps(state, quest, route)]
    if steps:
        return steps
    campaign = state.campaign
    if campaign is not None and act.region.id in campaign.resolved:
        return [QuestUpdated(quest=_completed(state, quest, act))]
    return [e for route in routes for e in _peace_deeds(state, quest, route, act.region)]


def _side_events(
    state: GameState, quest: Quest, tiers: DmTiers, catalogue: Registry[CatalogueItem]
) -> list[AnyEvent]:
    report = report_step_due(state, quest)
    if report is not None:  # M41.4 Z14: handed in where it was given, then it moves on
        return [QuestStepAdded(quest_id=quest.id, step=report)]
    done = quest.steps_done
    met = steps_met(state, quest.steps, done, quest.id)
    if met > done:
        return [
            QuestStepDone(quest_id=quest.id, step=i, log_line=quest.steps[i].text)
            for i in range(done, met)
        ]
    if not quest.steps or done < len(quest.steps):
        return []
    finished = quest.model_copy(update={"state": QuestState.COMPLETED})
    return [
        QuestUpdated(quest=finished),
        *quest_deed_events(state, finished, tiers),
        *quest_reward_events(state, finished, tiers, catalogue),
    ]


def quest_progress_events(
    state: GameState, tiers: DmTiers, catalogue: Registry[CatalogueItem]
) -> list[AnyEvent]:
    campaign = state.campaign
    events: list[AnyEvent] = []
    quests = state.world.quests
    if campaign is not None:
        plan = campaign.plan
        events += _backfill(state, plan)
        for act in plan.acts:
            main = quests.get(main_quest_id(act.region))
            if main is not None and main.state is QuestState.ACTIVE:
                events += _main_events(state, plan, act, main)
    events += _side_pass(state, events, tiers, catalogue)
    return chain_totals(state, events)


def _side_pass(
    state: GameState, before: list[AnyEvent], tiers: DmTiers, catalogue: Registry[CatalogueItem]
) -> list[AnyEvent]:
    touched = _moved_npcs(before)
    events: list[AnyEvent] = []
    for quest in sorted(state.world.quests.values(), key=lambda q: q.id):
        if quest.kind is QuestKind.MAIN or quest.state is not QuestState.ACTIVE:
            continue
        side = _side_events(state, quest, tiers, catalogue)
        npcs = _moved_npcs(side)
        if npcs & touched:
            continue  # its deeds build on the applied state of the next pass
        touched |= npcs
        events += side
    return events


def _moved_npcs(events: list[AnyEvent]) -> set[str]:
    return {e.npc_id for e in events if isinstance(e, AttitudeChanged)}


def route_effects(state: GameState, region: RegionPlan) -> frozenset[RouteEffect]:
    """The effects of the finished Cunning routes of `region`'s main quest (read by the offer)."""
    campaign = state.campaign
    quest = state.world.quests.get(main_quest_id(region))
    if campaign is None or quest is None:
        return frozenset()
    act = next((a for a in campaign.plan.acts if a.region.id == region.id), None)
    if act is None:
        return frozenset()
    effects: set[RouteEffect] = set()
    for route in main_quest(campaign.plan, act.index).routes:
        progress = quest.route(route.id)
        done = progress is not None and progress.steps_done >= len(route.steps)
        if route.effect is not None and done:
            effects.add(route.effect)
    return frozenset(effects)
