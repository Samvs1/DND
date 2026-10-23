"""Spoke milestones (M9.2, RULES_DECISIONS): XP for exploring and clearing a region's spokes.

Milestone XP is SRD-compatible ("milestone" advancement alongside kill XP) and engine-owned: the
amounts are data by the spoke's REGION tier (`DmTiers.milestone_xp`; M29.6b: they followed the
party level, so each level gained raised the next payout and the curve ran away). Each spoke pays
once for its first visit and once when it is cleared: a fight won there, or a successful parley with
what waited there. The paid sources are remembered in `CampaignState.milestones` (the reducer
records every milestone `RewardGranted`), so replays and repeats never pay twice.

Public API:
- `visit_key(node_id)`, `clear_key(node_id)`: the milestone sources.
- `spoke_region(state, node_id) -> RegionPlan | None`: the region whose spoke `node_id` is.
- `spoke_milestone_xp(tiers, region, key) -> int`: the XP per PC a `visit:` or `clear:` key pays.
- `spoke_milestone_events(state, key, amount, catalogue, already=0) -> list[AnyEvent]`: one
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
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterEnded
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world_events import PartyMoved
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


def spoke_milestone_xp(tiers: DmTiers, region: RegionPlan, key: str) -> int:
    row = tiers.milestone_xp[str(region.tier)]
    return row.visit if key.startswith("visit:") else row.clear


def spoke_milestone_events(
    state: GameState,
    key: str,
    amount: int,
    catalogue: Registry[CatalogueItem],
    already: int = 0,
) -> list[AnyEvent]:
    campaign = state.campaign
    if campaign is None or key in campaign.milestones:
        return []
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
    region = spoke_region(state, node)
    if node is None or region is None:
        return []
    keys: list[str] = []
    if any(isinstance(e, PartyMoved) and e.to_node == node for e in events):
        keys.append(visit_key(node))
    if any(_cleared(e) for e in events):
        keys.append(clear_key(node))
    out: list[AnyEvent] = []
    already = 0
    for key in keys:
        amount = spoke_milestone_xp(tiers, region, key)
        paid = spoke_milestone_events(state, key, amount, catalogue, already)
        if paid:
            out += paid
            already += amount
    return out
