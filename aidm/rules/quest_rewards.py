"""Quest lifecycle and milestone rewards (SPEC 9, 14 M5): the engine owns every number.

Lifecycle: offered -> active -> completed or failed (a quest can also lapse from offered to
failed); completed and failed are final. Completing a CAMPAIGN quest (one of the plan's quests)
pays its reward tier: XP per living PC by party level (`dm_tiers.xp_by_level`), gold by the quest
act's region tier (`quest_gold_gp`) shared among the PCs, and the plot item (`reward_item`,
inventory key `rules.secrets.item_key`). Quests the AI invents during play pay nothing, so a
model cannot farm XP by creating and completing quests; a favour (M23.5) never pays XP, gold or
items, even if its id matched a plan quest (its only reward is the asker's goodwill, a deed).

Milestones: a resolved region pays its tier's `milestone_xp` `region` XP (M29.6b: fixed per region
tier), and the final region adds `final_milestone_xp`. XP flags level-ups (`LevelUpReady`).

Public API:
- `quest_transition_refusal(old, new) -> str | None`: why the move is not allowed.
- `quest_payout(state, quest, tiers) -> Payout | None`: the reward of a completed plan quest.
- `quest_reward_events(state, quest, tiers, catalogue) -> list[AnyEvent]`: the payout events when
  `quest` is the new COMPLETED state of a quest that was not completed yet; call before the
  QuestUpdated is applied.
- `milestone_payout(state, resolved, tiers) -> Payout` and
  `resolution_reward_events(state, tiers, catalogue) -> list[AnyEvent]`:
  `progression.region_resolution_events` plus the milestone XP of every region it resolves (the
  session calls this instead of the bare function).
"""

from aidm.data.dm_tiers import DmTiers
from aidm.data.item_catalogue import CatalogueItem
from aidm.data.registry import Registry
from aidm.models.campaign import QuestPlan
from aidm.models.campaign_events import RegionResolved
from aidm.models.dm_tiers import XpTier
from aidm.models.events import AnyEvent
from aidm.models.quests import QuestKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.rules.dm_tiers import party_level, xp_award
from aidm.rules.progression import region_resolution_events
from aidm.rules.rewards import Payout, payout_events, reward_party
from aidm.rules.secrets import item_key

LIFECYCLE: dict[QuestState, frozenset[QuestState]] = {
    QuestState.OFFERED: frozenset({QuestState.ACTIVE, QuestState.FAILED}),
    QuestState.ACTIVE: frozenset({QuestState.COMPLETED, QuestState.FAILED}),
    QuestState.COMPLETED: frozenset(),
    QuestState.FAILED: frozenset(),
}


def quest_transition_refusal(old: QuestState | None, new: QuestState) -> str | None:
    if old is None or old is new:
        return None
    if new in LIFECYCLE[old]:
        return None
    if old is QuestState.OFFERED and new is QuestState.COMPLETED:
        return "the quest must be accepted (active) before it can be completed"
    return f"the quest is {old.value} and cannot become {new.value}"


def _plan_quest(state: GameState, quest_id: str) -> QuestPlan | None:
    campaign = state.campaign
    if campaign is None:
        return None
    return next((q for q in campaign.plan.quests if q.id == quest_id), None)


def quest_payout(state: GameState, quest: Quest, tiers: DmTiers) -> Payout | None:
    plan = _plan_quest(state, quest.id)
    if plan is None or quest.kind is not QuestKind.SIDE or quest.state is not QuestState.COMPLETED:
        return None
    party = reward_party(state)
    gold = tiers.quest_gold_gp[str(plan.act)][plan.reward_tier]
    items = (item_key(plan.reward_item),) if plan.reward_item else ()
    return Payout(
        xp_each=xp_award(tiers, XpTier(plan.reward_tier), party_level(state)),
        gold_total=gold * len(party),
        items=items,
    )


def quest_reward_events(
    state: GameState, quest: Quest, tiers: DmTiers, catalogue: Registry[CatalogueItem]
) -> list[AnyEvent]:
    old = state.world.quests.get(quest.id)
    if old is not None and old.state is QuestState.COMPLETED:
        return []
    payout = quest_payout(state, quest, tiers)
    if payout is None:
        return []
    return payout_events(state, payout, quest.id, "quest", catalogue)


def milestone_payout(state: GameState, resolved: RegionResolved, tiers: DmTiers) -> Payout:
    campaign = state.campaign
    region = (
        next(r for r in campaign.plan.all_regions() if r.id == resolved.region_id)
        if campaign
        else None
    )
    if region is None:
        return Payout()
    amount = tiers.milestone_xp[str(region.tier)].region
    if resolved.final:
        amount += tiers.final_milestone_xp
    return Payout(xp_each=amount)


def resolution_reward_events(
    state: GameState, tiers: DmTiers, catalogue: Registry[CatalogueItem]
) -> list[AnyEvent]:
    out: list[AnyEvent] = []
    already = 0
    for event in region_resolution_events(state):
        out.append(event)
        if isinstance(event, RegionResolved):
            payout = milestone_payout(state, event, tiers)
            out.extend(
                payout_events(state, payout, event.region_id, "milestone", catalogue, already)
            )
            already += payout.xp_each
    return out
