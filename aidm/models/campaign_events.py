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
- `OfferResolved(offer_id, choice, success, detail, foes)`: the pending offer is answered; its
  consequences (a check, a retreat, an attitude change, the fight) are separate events; `foes`
  (M32.1b X14) are the offer's monster ids, so the telling knows who was answered.
- `EpilogueWritten(text, source)` (M5.7): the epilogue of the finished campaign (`source` is
  "model", "template" or "mixed"); stored in `CampaignState.epilogue`, so a reconnect can show it.
- `FinaleChosen(option_id)` (M23.9): the party chose one of the plan's two endings (after the
  final region resolved, confirmed on the phone); the campaign is complete after it.
- `DifficultySet(monster_hp, monster_damage)` (M6.5): the host's difficulty multipliers
  (`GameState.difficulty`).
- `CampaignEvents`: the union of these classes (joins `AnyEvent`).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.campaign import CampaignPlan
from aidm.models.campaign_state import EncounterOffer, OfferChoice, RegionResolution
from aidm.models.difficulty import MAX_MULTIPLIER, MIN_MULTIPLIER
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
    foes: tuple[str, ...] = ()  # M32.1b X14: the offer's monster ids (who the answer was to)


class EpilogueWritten(_CampaignEvent):
    type: Literal["epilogue_written"] = "epilogue_written"
    text: str = Field(min_length=1)
    source: Literal["model", "template", "mixed"]


class FinaleChosen(_CampaignEvent):
    type: Literal["finale_chosen"] = "finale_chosen"
    option_id: str = Field(min_length=1)


class DifficultySet(_CampaignEvent):
    type: Literal["difficulty_set"] = "difficulty_set"
    monster_hp: float = Field(ge=MIN_MULTIPLIER, le=MAX_MULTIPLIER)
    monster_damage: float = Field(ge=MIN_MULTIPLIER, le=MAX_MULTIPLIER)


CampaignEvents = (
    CampaignInstalled
    | RegionResolved
    | EncounterOffered
    | OfferResolved
    | EpilogueWritten
    | FinaleChosen
    | DifficultySet
)
