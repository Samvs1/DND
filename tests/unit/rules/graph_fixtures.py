"""Builders for region plans and worlds used by the region graph tests (M5.2)."""

from __future__ import annotations

from aidm.models.campaign import BossPlan, NodePlan, RegionPlan
from aidm.models.region_graph import GraphEdge, RegionGraph
from aidm.models.world import World
from aidm.rules.world_graph import graph_neighbours, locked_nodes_for


def _node(node_id: str, themes: tuple[str, ...] = ("goblin",)) -> NodePlan:
    return NodePlan(
        id=node_id,
        name=node_id.title(),
        flavour="A place.",
        terrain_tags=("wilds",),
        encounter_themes=themes,
    )


def region_plan(spoke_count: int, region_id: str = "r1") -> RegionPlan:
    gate = f"{region_id}-gate"
    return RegionPlan(
        id=region_id,
        name="Region",
        flavour="A region.",
        tier=1,
        terrain_tags=("wilds",),
        arrival=_node(f"{region_id}-arrival", ()),
        spokes=tuple(_node(f"{region_id}-spoke{i}") for i in range(spoke_count)),
        gateway=_node(gate, ()),
        boss=BossPlan(monster_id="bugbear", name="Boss", lair_node=gate),
    )


def hand_graph(
    edges: list[GraphEdge], spokes: tuple[str, ...] = ("a", "b"), boss_lair: str = "g"
) -> RegionGraph:
    return RegionGraph(
        region_id="hand",
        tier=1,
        arrival="s",
        spokes=spokes,
        gateway="g",
        nodes=("s", *spokes, "g"),
        edges=tuple(edges),
        boss_id="bugbear",
        boss_lair=boss_lair,
    )


def world_at(graph: RegionGraph, node: str, visited: frozenset[str]) -> World:
    """The world fields the graph derives for a party standing at `node`."""
    return World(
        current_node=node,
        neighbours=graph_neighbours(graph.edges),
        locked_nodes=locked_nodes_for(graph.edges, visited),
        visited=sorted(visited),
    )
