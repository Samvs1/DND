"""Campaign progress state: the installed plan, its graph and how far the party got (SPEC 9).

Set by `CampaignInstalled` (M5.3) and advanced by the progression events (M5.4). Server-side
only: the plan holds NPC motives and secrets, which never reach a client (`aidm.rules.social`
`public_npc_view` is the client projection of an NPC).

Public API:
- `RegionResolution`: defeat / alliance (how a region's boss was resolved).
- `OfferChoice`: fight / surprise / escape / parley (the options of a world-pulled encounter).
- `EncounterOffer(id, node_id, region_id, monster_ids, boss_npc_id, difficulty, retreat_node,
  escape_dc, parley_dc, surprise_dc, options)`: the warning beat before a fight: what waits
  at the node and the DCs the engine set; nothing has started yet.
- `CampaignState(plan, graph, seed, resolved, complete, offered_nodes, offer, epilogue,
  milestones, finale_choice)`: `resolved`
  maps region id -> resolution, `complete` is set when the final region is resolved (with a
  finale in the plan the story ends only once `finale_choice` holds the chosen ending's id,
  M23.9: `aidm.rules.progression.campaign_complete` is the one reading of "the story is over"),
  `offered_nodes` are nodes whose one-time encounter was already offered, `offer` is the
  pending offer (the party must answer it before anything else happens there); `epilogue` is
  the written epilogue of a completed campaign (M5.7); `milestones` are the sources of the
  milestone rewards already paid (M9.2: `visit:<node>`, `clear:<node>`, region ids).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.campaign import CampaignPlan
from aidm.models.region_graph import CampaignGraph


class RegionResolution(StrEnum):
    DEFEAT = "defeat"
    ALLIANCE = "alliance"


class OfferChoice(StrEnum):
    FIGHT = "fight"
    SURPRISE = "surprise"
    ESCAPE = "escape"
    PARLEY = "parley"


class EncounterOffer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    monster_ids: tuple[str, ...] = ()
    boss_npc_id: str | None = None
    difficulty: str = "trivial"
    retreat_node: str | None = None
    escape_dc: int = Field(ge=0)
    parley_dc: int = Field(ge=0)
    surprise_dc: int = Field(ge=0)
    options: tuple[OfferChoice, ...] = tuple(OfferChoice)


class CampaignState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: CampaignPlan
    graph: CampaignGraph
    seed: int = 0
    resolved: dict[str, RegionResolution] = Field(default_factory=dict[str, RegionResolution])
    complete: bool = False
    offered_nodes: list[str] = Field(default_factory=list[str])
    offer: EncounterOffer | None = None
    epilogue: str | None = None
    milestones: list[str] = Field(default_factory=list[str])
    finale_choice: str | None = None
