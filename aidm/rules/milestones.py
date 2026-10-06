"""Spoke milestones (M9.2, RULES_DECISIONS): XP for exploring and clearing a region's spokes.

Milestone XP is SRD-compatible ("milestone" advancement alongside kill XP) and engine-owned: the
tier names come from data (`DmTiers.spoke_visit_xp_tier`, `spoke_clear_xp_tier`) and the amount
from the same `xp_by_level` table every `grant_xp` uses, by party level. Each spoke pays once
for its first visit and once when it is cleared: a fight won there, or a successful parley with
what waited there. The paid sources are remembered in `CampaignState.milestones` (the reducer
records every milestone `RewardGranted`), so replays and repeats never pay twice.

Public API:
- `visit_key(node_id)`, `clear_key(node_id)`: the milestone sources.
- `spoke_region(state, node_id) -> RegionPlan | None`: the region whose spoke `node_id` is.
- `spoke_milestone_events(state, key, tier, tiers, catalogue, already=0) -> list[AnyEvent]`: one
  payout (`[]` when `key` was paid already); `already` as in `rules.rewards.payout_events`.
- `milestone_events(state, events, tiers, catalogue) -> list[AnyEvent]`: the milestones an
  APPLIED batch earned: `PartyMoved` -> first visit of the new node; `EncounterEnded` with
  VICTORY or a successful parley `OfferResolved` -> the current node is cleared.
"""

from collections.abc import Sequence

from aidm.data.dm_tiers import DmTiers
from aidm.data.item_catalogue import CatalogueItem
from aidm.data.registry import Registry
from aidm.models.campaign import RegionPlan
from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.dm_tiers import XpTier
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterEnded
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world_events import PartyMoved
from aidm.rules.dm_tiers import party_level, xp_award
from aidm.rules.rewards import Payout, payout_events


def visit_key(node_id: str) -> str:
    return f"visit:{node_id}"


def clear_key(node_id: str) -> str:
    return f"clear:{node_id}"


def spoke_region(state: GameState, node_id: str | None) -> RegionPlan | None:
    campaign = state.campaign
    if campaign is None or node_id is None:
        return None
    for region in campaign.plan.all_regions():
        if any(spoke.id == node_id for spoke in region.spokes):
            return region
    return None


def spoke_milestone_events(
    state: GameState,
    key: str,
    tier: str,
    tiers: DmTiers,
    catalogue: Registry[CatalogueItem],
    already: int = 0,
) -> list[AnyEvent]:
    campaign = state.campaign
    if campaign is None or key in campaign.milestones:
        return []
    amount = xp_award(tiers, XpTier(tier), party_level(state))
    return payout_events(state, Payout(xp_each=amount), key, "milestone", catalogue, already)


def _cleared(event: AnyEvent) -> bool:
    if isinstance(event, EncounterEnded):
        return event.status is EncounterStatus.VICTORY
    return (
        isinstance(event, OfferResolved)
        and event.choice is OfferChoice.PARLEY
        and event.success is True
    )


def milestone_events(
    state: GameState,
    events: Sequence[AnyEvent],
    tiers: DmTiers,
    catalogue: Registry[CatalogueItem],
) -> list[AnyEvent]:
    node = state.world.current_node
    if node is None or spoke_region(state, node) is None:
        return []
    keys: list[tuple[str, str]] = []
    if any(isinstance(e, PartyMoved) and e.to_node == node for e in events):
        keys.append((visit_key(node), tiers.spoke_visit_xp_tier))
    if any(_cleared(e) for e in events):
        keys.append((clear_key(node), tiers.spoke_clear_xp_tier))
    out: list[AnyEvent] = []
    already = 0
    for key, tier in keys:
        paid = spoke_milestone_events(state, key, tier, tiers, catalogue, already)
        if paid:
            out += paid
            already += xp_award(tiers, XpTier(tier), party_level(state))
    return out
