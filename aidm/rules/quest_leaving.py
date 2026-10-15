"""Leaving a region with open tasks (M23.4, GOAL "Lifecycle: act change"). Pure: returns events.

Regions are one-way (gateway -> the next region's arrival), so a side quest or favour cannot be
carried over. The region of a quest is its plan act's region (`QuestPlan.act`; old plans whose
giver lives elsewhere still count by act), else the region of its giver's place (favours, quests
the model made up); main quests never close here.

- Crossing asks first: `crossing(state, to_node)` names the next region and the open tasks of
  the current one (offered or active, not every step done) when the move leaves the region; the
  move tool turns it into the same point-of-no-return confirmation as a hostile act.
- After the move (and in old saves that already crossed), `left_behind_events` closes every open
  task of an earlier act's region as failed with `closed_reason=left_behind` (no deed, no
  penalty) and drops that region's leads. The session runs it once the quest passes moved
  nothing, so a task whose steps were all done completes (and pays) first. An OFFERED quest
  whose giver lives in a region the party left closes the same way (M23.5: that giver can never
  ask again; the playtest's act-2 quest given at the act-1 gateway).

Public API: `quest_region_id(state, quest)`, `Crossing(region, quests)`,
`crossing(state, to_node) -> Crossing | None`, `crossing_prompt(crossing) -> str`,
`left_behind_events(state) -> list[AnyEvent]`.
"""

from dataclasses import dataclass

from aidm.models.campaign import CampaignPlan, RegionPlan
from aidm.models.events import AnyEvent
from aidm.models.quest_events import QuestLeadRemoved
from aidm.models.quests import QuestKind
from aidm.models.state import GameState
from aidm.models.world import MAX_QUEST_LOG, ClosedReason, Quest, QuestState
from aidm.models.world_events import QuestUpdated
from aidm.rules.progression import region_of
from aidm.rules.quest_progress import current_act
from aidm.rules.quest_steps import steps_met

OPEN = (QuestState.OFFERED, QuestState.ACTIVE)
LEFT_LINE = "Left behind on leaving {region}."


@dataclass(frozen=True)
class Crossing:
    region: RegionPlan
    quests: tuple[Quest, ...]


def _plan_region(plan: CampaignPlan, quest_id: str) -> str | None:
    planned = next((q for q in plan.quests if q.id == quest_id), None)
    if planned is None:
        return None
    act = next((a for a in plan.acts if a.index == planned.act), None)
    return act.region.id if act is not None else None


def quest_region_id(state: GameState, quest: Quest) -> str | None:
    campaign = state.campaign
    if campaign is None or quest.kind is QuestKind.MAIN:
        return None
    planned = _plan_region(campaign.plan, quest.id)
    if planned is not None:
        return planned
    return _giver_region_id(state, quest)


def _giver_region_id(state: GameState, quest: Quest) -> str | None:
    giver = state.world.npcs.get(quest.giver_npc_id or "")
    region = region_of(state, giver.node_id) if giver is not None else None
    return region.id if region is not None else None


def _all_done(state: GameState, quest: Quest) -> bool:
    if not quest.steps or quest.state is not QuestState.ACTIVE:
        return False
    return steps_met(state, quest.steps, quest.steps_done, quest.id) >= len(quest.steps)


def _open_in(state: GameState, region_id: str) -> tuple[Quest, ...]:
    quests = sorted(state.world.quests.values(), key=lambda q: q.id)
    return tuple(
        q
        for q in quests
        if q.state in OPEN and quest_region_id(state, q) == region_id and not _all_done(state, q)
    )


def crossing(state: GameState, to_node: str) -> Crossing | None:
    here = region_of(state, state.world.current_node)
    there = region_of(state, to_node)
    if here is None or there is None or here.id == there.id:
        return None
    quests = _open_in(state, here.id)
    return Crossing(region=there, quests=quests) if quests else None


def crossing_prompt(cross: Crossing) -> str:
    titles = ", ".join(q.title for q in cross.quests)
    return f"Crossing into {cross.region.name} leaves these behind: {titles}. Go on?"


def _closed(quest: Quest, region: str) -> Quest:
    log = (*quest.log, LEFT_LINE.format(region=region))[-MAX_QUEST_LOG:]
    update = {"state": QuestState.FAILED, "closed_reason": ClosedReason.LEFT_BEHIND, "log": log}
    return quest.model_copy(update=update)


def left_behind_events(state: GameState) -> list[AnyEvent]:
    campaign = state.campaign
    act = current_act(state)
    if campaign is None or act is None:
        return []
    earlier = {a.region.id: a.region.name for a in campaign.plan.acts if a.index < act}
    events: list[AnyEvent] = []
    for quest in sorted(state.world.quests.values(), key=lambda q: q.id):
        region = quest_region_id(state, quest) if quest.state in OPEN else None
        if region not in earlier and quest.state is QuestState.OFFERED:
            region = _giver_region_id(state, quest)  # M23.5: that giver can never ask now
        if region is not None and region in earlier:
            events.append(QuestUpdated(quest=_closed(quest, earlier[region])))
    events += [
        QuestLeadRemoved(quest_id=lead.quest_id)
        for lead in state.world.leads
        if _plan_region(campaign.plan, lead.quest_id) in earlier
    ]
    return events
