"""Why a way is shut (M23.8, GOAL_QUESTS "What players see", last bullet). Pure.

A locked node is a world fact, not a hint, so the refusal says why in world terms:
- the gateway of the party's region while spokes are unvisited: "<gateway> stays shut while
  <region> still hides places you have not seen: <N> left." The unvisited spokes are named when
  every one of them is a known exit (a neighbour of a place the party has seen), else only the
  count is told;
- the arrival of the next region while the party's region is unresolved: "The way on opens once
  the master of <region> is dealt with.";
- anything else locked: "The way to <place> is barred for now."

Public API: `locked_reason(state, node_id) -> str | None` (None: the node is not locked),
`short_reason(state, node_id) -> str` (the few words for an exit label in the AI context),
`gateway_need(state, region) -> str | None` (M31.1b V12: the gateway line while its spokes are
unseen, the same rule the lock uses; None: the gateway is open to the party).
"""

from aidm.models.campaign import RegionPlan
from aidm.models.state import GameState
from aidm.rules.progression import region_of
from aidm.rules.scene import node_display_name

GATEWAY_SHUT = "{gateway} stays shut while {region} still hides places you have not seen: {left}."
WAY_ON_SHUT = "The way on opens once the master of {region} is dealt with."
BARRED = "The way to {place} is barred for now."


def _next_arrival(state: GameState, region: RegionPlan) -> str | None:
    campaign = state.campaign
    if campaign is None:
        return None
    acts = campaign.plan.acts
    index = next((i for i, a in enumerate(acts) if a.region.id == region.id), None)
    if index is None or index + 1 >= len(acts):
        return None
    return acts[index + 1].region.arrival.id


def _known(state: GameState, node_id: str) -> bool:
    world = state.world
    return any(node_id in world.neighbours.get(seen, ()) for seen in world.visited)


def _unseen(state: GameState, region: RegionPlan) -> str:
    unseen = [s.id for s in region.spokes if s.id not in state.world.visited]
    count = f"{len(unseen)} left"
    if not all(_known(state, node) for node in unseen):
        return count
    names = ", ".join(node_display_name(state, node) for node in unseen)
    return f"{count} ({names})"


def gateway_need(state: GameState, region: RegionPlan) -> str | None:
    """The gateway of `region` stays shut while it has spokes the party has not seen."""
    if all(s.id in state.world.visited for s in region.spokes):
        return None
    gateway = node_display_name(state, region.gateway.id)
    return GATEWAY_SHUT.format(gateway=gateway, region=region.name, left=_unseen(state, region))


def locked_reason(state: GameState, node_id: str) -> str | None:
    world = state.world
    if node_id not in world.locked_nodes:
        return None
    region = region_of(state, world.current_node)
    campaign = state.campaign
    if region is not None and campaign is not None:
        need = gateway_need(state, region)
        if node_id == region.gateway.id and need is not None:
            return need
        unresolved = region.id not in campaign.resolved
        if node_id == _next_arrival(state, region) and unresolved:
            return WAY_ON_SHUT.format(region=region.name)
    return BARRED.format(place=node_display_name(state, node_id))


def short_reason(state: GameState, node_id: str) -> str:
    """The lock and its reason in a few words, for an exit label ("locked until ...")."""
    region = region_of(state, state.world.current_node)
    if region is not None and node_id == region.gateway.id:
        left = sum(1 for s in region.spokes if s.id not in state.world.visited)
        if left:
            return f"locked until every place of {region.name} is seen, {left} left"
    if region is not None and node_id == _next_arrival(state, region):
        return f"locked until the master of {region.name} is dealt with"
    return "locked"
