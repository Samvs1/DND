"""M5.2: region graph builder, validation, locks and travel helpers."""

from __future__ import annotations

from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.region_graph import GraphEdge
from aidm.rules.world_graph import (
    build_campaign_graph,
    build_region_graph,
    graph_neighbours,
    legal_neighbours,
    locked_nodes_for,
    validate_campaign_graph,
    validate_region,
)
from tests.unit.rules.graph_fixtures import hand_graph, region_plan, world_at

PLAN = load_sample_campaign()


def _edge(src: str, dst: str, *needs: str) -> GraphEdge:
    return GraphEdge(src=src, dst=dst, requires_visited=needs)


def test_build_is_deterministic_and_seeded() -> None:
    region = region_plan(3)
    assert build_region_graph(region, 7) == build_region_graph(region, 7)
    variants = {build_region_graph(region, s).edges for s in range(12)}
    assert len(variants) > 1


def test_arrival_connects_to_every_spoke_and_gateway_is_locked() -> None:
    graph = build_region_graph(region_plan(3), 1)
    exits = graph_neighbours(graph.edges)
    assert set(graph.spokes) <= set(exits[graph.arrival])
    assert graph.gateway not in exits[graph.arrival]
    into_gate = [e for e in graph.edges if e.dst == graph.gateway]
    assert {e.src for e in into_gate} == set(graph.spokes)
    assert all(set(e.requires_visited) == set(graph.spokes) for e in into_gate)
    assert graph.boss_lair == graph.gateway


def test_sample_campaign_graphs_are_valid() -> None:
    for seed in range(5):
        graph = build_campaign_graph(PLAN, seed)
        assert validate_campaign_graph(graph) == []
        assert len(graph.links) == 2


def test_inter_act_link_needs_resolution() -> None:
    graph = build_campaign_graph(PLAN)
    first, second = graph.regions[0], graph.regions[1]
    link = graph.links[0]
    assert (link.src, link.dst) == (first.gateway, second.arrival)
    edges = graph.all_edges()
    visited = {first.arrival, *first.spokes, first.gateway}
    assert second.arrival in locked_nodes_for(edges, visited)
    assert second.arrival not in locked_nodes_for(edges, visited, {first.region_id})


def test_gateway_unlocks_when_all_spokes_visited() -> None:
    graph = build_region_graph(region_plan(3), 2)
    spokes = list(graph.spokes)
    assert graph.gateway in locked_nodes_for(graph.edges, {graph.arrival})
    assert graph.gateway in locked_nodes_for(graph.edges, {graph.arrival, *spokes[:2]})
    assert graph.gateway not in locked_nodes_for(graph.edges, {graph.arrival, *spokes})


def test_legal_neighbours_hides_the_locked_gateway() -> None:
    graph = build_region_graph(region_plan(2), 0)
    first, second = graph.spokes
    early = world_at(graph, first, frozenset({graph.arrival, first}))
    assert graph.gateway not in legal_neighbours(early, first)
    assert graph.arrival in legal_neighbours(early, first)
    late = world_at(graph, second, frozenset({graph.arrival, first, second}))
    assert graph.gateway in legal_neighbours(late, second)
    assert legal_neighbours(late, None) == ()
    assert legal_neighbours(late, "nowhere") == ()


def test_valid_hand_graph_has_no_problems() -> None:
    edges = [_edge("s", "a"), _edge("a", "s"), _edge("s", "b"), _edge("b", "s")]
    edges += [_edge("a", "g", "a", "b"), _edge("b", "g", "a", "b"), _edge("g", "s")]
    assert validate_region(hand_graph(edges)) == []


def test_disconnected_spoke_is_reported() -> None:
    edges = [_edge("s", "a"), _edge("a", "s"), _edge("a", "g", "a", "b"), _edge("g", "s")]
    codes = {p.code for p in validate_region(hand_graph(edges))}
    assert "unreachable_node" in codes
    assert "gateway_unreachable" in codes


def test_softlock_is_reported() -> None:
    # the gateway only needs spoke a, but spoke b is a one-way dead end: entering it traps the party
    edges = [_edge("s", "a"), _edge("a", "s"), _edge("s", "b"), _edge("a", "g", "a")]
    edges += [_edge("g", "s")]
    problems = validate_region(hand_graph(edges))
    assert [p.code for p in problems] == ["softlock"]
    assert problems[0].subject == "b"


def test_boss_must_wait_at_the_gateway() -> None:
    edges = [_edge("s", "a"), _edge("a", "s"), _edge("s", "b"), _edge("b", "s")]
    edges += [_edge("a", "g", "a", "b"), _edge("b", "g", "a", "b")]
    codes = [p.code for p in validate_region(hand_graph(edges, boss_lair="a"))]
    assert codes == ["boss_not_at_gateway"]


def test_unknown_node_and_bad_shape_are_reported() -> None:
    codes = {p.code for p in validate_region(hand_graph([_edge("s", "zzz")]))}
    assert codes == {"unknown_node"}
    assert "bad_shape" in {p.code for p in validate_region(hand_graph([], spokes=("a", "a")))}


def test_gateway_gated_by_resolution_is_reported() -> None:
    edges = [GraphEdge(src="a", dst="g", requires_resolved=("hand",))]
    codes = {p.code for p in validate_region(hand_graph(edges))}
    assert "boss_gated" in codes


def test_campaign_link_errors_are_reported() -> None:
    graph = build_campaign_graph(PLAN)
    broken = graph.model_copy(update={"links": graph.links[:1]})
    assert [p.code for p in validate_campaign_graph(broken)] == ["bad_link"]
    swapped = graph.model_copy(update={"links": tuple(reversed(graph.links))})
    assert {p.code for p in validate_campaign_graph(swapped)} == {"bad_link"}
