"""Reducer part for the campaign events (called only by `aidm.session.reducer.apply`).

Travel locks are derived state: after the campaign is installed, after every `PartyMoved`
(`aidm.session.world_apply`) and after every `RegionResolved`, `refresh_travel` recomputes
`World.locked_nodes` from the campaign graph (`aidm.rules.world_graph.locked_nodes_for`) and sets
`World.region_tier` to the tier of the party's region. Both are pure functions of state already
in the log, so replay stays exact (DECISIONS M5.4).

Public API: `CAMPAIGN_EVENT_TYPES`, `apply_campaign_event(state, event)`,
`refresh_travel(state)`.
"""

from typing import assert_never

from aidm.models.campaign_events import (
    CampaignInstalled,
    DifficultySet,
    EncounterOffered,
    EpilogueWritten,
    FinaleChosen,
    OfferResolved,
    RegionResolved,
)
from aidm.models.campaign_state import CampaignState
from aidm.models.difficulty import Difficulty
from aidm.models.state import GameState
from aidm.rules.world_graph import graph_neighbours, locked_nodes_for
from aidm.session.reducer_errors import ReducerError

type CampaignEvent = (
    CampaignInstalled
    | RegionResolved
    | EncounterOffered
    | OfferResolved
    | EpilogueWritten
    | FinaleChosen
    | DifficultySet
)

CAMPAIGN_EVENT_TYPES = (
    CampaignInstalled,
    RegionResolved,
    EncounterOffered,
    OfferResolved,
    EpilogueWritten,
    FinaleChosen,
    DifficultySet,
)


def _campaign(state: GameState) -> CampaignState:
    if state.campaign is None:
        raise ReducerError("no campaign is installed")
    return state.campaign


def refresh_travel(state: GameState) -> None:
    campaign = state.campaign
    if campaign is None:
        return
    world = state.world
    edges = campaign.graph.all_edges()
    world.locked_nodes = locked_nodes_for(edges, world.visited, set(campaign.resolved))
    for region in campaign.graph.regions:
        if world.current_node in region.nodes:
            world.region_tier = region.tier


def _installed(state: GameState, event: CampaignInstalled) -> None:
    if state.campaign is not None:
        raise ReducerError("a campaign is already installed")
    state.campaign = CampaignState(plan=event.plan, graph=event.graph, seed=event.seed)
    world = state.world
    world.neighbours = graph_neighbours(event.graph.all_edges())
    world.node_names.update({n.id: n.name for n in event.plan.all_nodes()})
    lore = [event.plan.title, *(r.name for r in event.plan.all_regions())]
    world.lore_names = [*world.lore_names, *(n for n in lore if n not in world.lore_names)]
    refresh_travel(state)


def _finale_chosen(campaign: CampaignState, option_id: str) -> None:
    finale = campaign.plan.finale
    if finale is None or not campaign.complete or campaign.finale_choice is not None:
        raise ReducerError("no finale is waiting for a choice")
    if option_id not in {o.id for o in finale.options}:
        raise ReducerError(f"unknown ending {option_id!r}")
    campaign.finale_choice = option_id


def apply_campaign_event(state: GameState, event: CampaignEvent) -> None:
    match event:
        case CampaignInstalled():
            _installed(state, event)
        case RegionResolved(region_id=region_id, how=how, final=final):
            campaign = _campaign(state)
            if region_id not in {r.region_id for r in campaign.graph.regions}:
                raise ReducerError(f"unknown region {region_id!r}")
            campaign.resolved[region_id] = how
            campaign.complete = campaign.complete or final
            refresh_travel(state)
        case EncounterOffered(offer=offer):
            campaign = _campaign(state)
            if campaign.offer is not None:
                raise ReducerError("an encounter offer is already pending")
            campaign.offer = offer
            if offer.node_id not in campaign.offered_nodes:
                campaign.offered_nodes.append(offer.node_id)
        case OfferResolved(offer_id=offer_id):
            campaign = _campaign(state)
            if campaign.offer is None or campaign.offer.id != offer_id:
                raise ReducerError(f"no pending encounter offer {offer_id!r}")
            campaign.offer = None
        case EpilogueWritten(text=text):
            campaign = _campaign(state)
            if not campaign.complete:
                raise ReducerError("the campaign is not complete")
            campaign.epilogue = text
        case FinaleChosen(option_id=option_id):
            _finale_chosen(_campaign(state), option_id)
        case DifficultySet(monster_hp=hp, monster_damage=damage):
            state.difficulty = Difficulty(monster_hp=hp, monster_damage=damage)
        case _:
            assert_never(event)
