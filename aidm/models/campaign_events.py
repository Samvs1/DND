"""Campaign events (part of the `aidm.models.events.Event` union; same design rules apply).

Emitted by `aidm.rules.campaign_install` and `aidm.rules.progression` and applied by
`aidm.session.campaign_apply`.

Public API:
- `CampaignInstalled(plan, graph, seed)`: the campaign exists: the world gets the graph's
  neighbours, node names and lore names (NPCs, quests and the first move are separate events).
- `RegionResolved(region_id, how, final)`: the region's boss was defeated or allied; the next
  act's arrival unlocks; `final` marks the campaign complete (epilogue in M5.7).
- `EncounterOffered(offer)`: the warning beat of a world-pulled encounter (the node is now
  offered; the party must choose fight / surprise / escape / parley).
- `OfferResolved(offer_id, choice, success, detail)`: the pending offer is answered; its
  consequences (a check, a retreat, an attitude change, the fight) are separate events.
- `CampaignEvents`: the union of these classes (joins `AnyEvent`).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.campaign import CampaignPlan
from aidm.models.campaign_state import EncounterOffer, OfferChoice, RegionResolution
from aidm.models.region_graph import CampaignGraph


class _CampaignEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CampaignInstalled(_CampaignEvent):
    type: Literal["campaign_installed"] = "campaign_installed"
    plan: CampaignPlan
    graph: CampaignGraph
    seed: int = 0


class RegionResolved(_CampaignEvent):
    type: Literal["region_resolved"] = "region_resolved"
    region_id: str = Field(min_length=1)
    how: RegionResolution
    final: bool = False


class EncounterOffered(_CampaignEvent):
    type: Literal["encounter_offered"] = "encounter_offered"
    offer: EncounterOffer


class OfferResolved(_CampaignEvent):
    type: Literal["offer_resolved"] = "offer_resolved"
    offer_id: str = Field(min_length=1)
    choice: OfferChoice
    success: bool | None = None
    detail: str = ""


CampaignEvents = CampaignInstalled | RegionResolved | EncounterOffered | OfferResolved
