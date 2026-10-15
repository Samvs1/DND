"""Region graph builder, progression checks and travel helpers (SPEC 9, M5.2). Pure.

A region is a hub with spokes and a gateway, built by code and never by the AI:
- the arrival node connects both ways to every spoke; spokes may connect to each other (a seeded
  coin per pair, deterministic for a seed and region id);
- the gateway (the boss's lair) is entered from the spokes only, and only after ALL spokes were
  visited (`requires_visited` on those edges); it leads back to the spokes and the arrival
  without a lock, and the boss can always be fought there (defeat is always possible);
- the gateway of act N leads to the arrival of act N+1 once region N is resolved.

Public API:
- `build_region_graph(region, seed=0) -> RegionGraph`, `build_campaign_graph(plan, seed=0)`.
- `validate_region(graph) -> list[Problem]`: codes `duplicate_node`, `bad_shape`, `unknown_node`,
  `bad_lock`, `no_boss`, `boss_not_at_gateway`, `boss_gated`, `unreachable_node`,
  `spoke_behind_gateway`, `gateway_unreachable`, `softlock` (empty list: valid).
- `validate_campaign_graph(graph) -> list[Problem]` (every region plus the act links).
- Travel helpers for the world state: `graph_neighbours(edges) -> dict[node, [dst...]]`,
  `locked_nodes_for(edges, visited, resolved=()) -> list[node]` (a node is locked while every edge
  into it is closed; the gateway unlocks when all spokes are visited), and
  `legal_neighbours(world, node) -> tuple[node, ...]` (the exits `move_party` may use now) and
  `travel_route(world, start, goal) -> tuple[node, ...] | None` (M23.8: the shortest walk over
  the legal exits as they stand now, goal included, start excluded; None when the way is shut).
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Collection, Iterable
from itertools import combinations

from aidm.models.campaign import CampaignPlan, RegionPlan
from aidm.models.problem import Problem
from aidm.models.region_graph import CampaignGraph, GraphEdge, RegionGraph
from aidm.models.world import World

type State = tuple[str, frozenset[str]]


def _both(a: str, b: str) -> tuple[GraphEdge, GraphEdge]:
    return GraphEdge(src=a, dst=b), GraphEdge(src=b, dst=a)


def build_region_graph(region: RegionPlan, seed: int = 0) -> RegionGraph:
    rng = random.Random(f"{seed}:{region.id}")
    arrival, gateway = region.arrival.id, region.gateway.id
    spokes = tuple(s.id for s in region.spokes)
    edges: list[GraphEdge] = []
    for spoke in spokes:
        edges.extend(_both(arrival, spoke))
    for a, b in combinations(spokes, 2):
        if rng.random() < 0.5:
            edges.extend(_both(a, b))
    for spoke in spokes:
        edges.append(GraphEdge(src=spoke, dst=gateway, requires_visited=spokes))
        edges.append(GraphEdge(src=gateway, dst=spoke))
    edges.append(GraphEdge(src=gateway, dst=arrival))
    return RegionGraph(
        region_id=region.id,
        tier=region.tier,
        arrival=arrival,
        spokes=spokes,
        gateway=gateway,
        nodes=tuple(n.id for n in region.nodes()),
        edges=tuple(edges),
        boss_id=region.boss.monster_id,
        boss_lair=region.boss.lair_node,
    )


def build_campaign_graph(plan: CampaignPlan, seed: int = 0) -> CampaignGraph:
    regions = tuple(build_region_graph(r, seed) for r in plan.all_regions())
    links = tuple(
        GraphEdge(src=a.gateway, dst=b.arrival, requires_resolved=(a.region_id,))
        for a, b in zip(regions, regions[1:], strict=False)
    )
    return CampaignGraph(regions=regions, links=links)


def _open(edge: GraphEdge, visited: Collection[str], resolved: Collection[str]) -> bool:
    return all(n in visited for n in edge.requires_visited) and all(
        r in resolved for r in edge.requires_resolved
    )


def _explore(graph: RegionGraph) -> tuple[set[State], dict[State, list[State]]]:
    """Every (current node, visited set) the party can be in, and the moves between them."""
    start: State = (graph.arrival, frozenset({graph.arrival}))
    by_src: dict[str, list[GraphEdge]] = {}
    for edge in graph.edges:
        by_src.setdefault(edge.src, []).append(edge)
    moves: dict[State, list[State]] = {}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        if state in moves:
            continue
        node, visited = state
        moves[state] = [
            (e.dst, visited | {e.dst}) for e in by_src.get(node, ()) if _open(e, visited, ())
        ]
        queue.extend(moves[state])
    return set(moves), moves


def _shape(graph: RegionGraph) -> list[Problem]:
    out: list[Problem] = []
    nodes = set(graph.nodes)
    if len(nodes) != len(graph.nodes):
        out.append(Problem(code="duplicate_node", message="a node id is listed twice"))
    parts = [graph.arrival, graph.gateway, *graph.spokes]
    if len(set(parts)) != len(parts) or set(parts) != nodes:
        msg = "nodes must be exactly one arrival, the spokes and one gateway, all different"
        out.append(Problem(code="bad_shape", message=msg))
    return out


def _structure(graph: RegionGraph) -> list[Problem]:
    out = _shape(graph)
    nodes = set(graph.nodes)
    for edge in graph.edges:
        for end in (edge.src, edge.dst, *edge.requires_visited):
            if end not in nodes:
                msg = f"edge {edge.src}->{edge.dst} names unknown node {end!r}"
                out.append(Problem(code="unknown_node", message=msg, subject=end))
        if edge.dst == graph.gateway and edge.requires_resolved:
            msg = "the boss's lair cannot require the region to be resolved"
            out.append(Problem(code="boss_gated", message=msg, subject=graph.gateway))
        if edge.dst in edge.requires_visited:
            msg = f"edge {edge.src}->{edge.dst} requires its own destination"
            out.append(Problem(code="bad_lock", message=msg, subject=edge.dst))
    return out


def _boss(graph: RegionGraph) -> list[Problem]:
    if not graph.boss_id:
        return [Problem(code="no_boss", message="the region has no boss", subject=graph.gateway)]
    if graph.boss_lair != graph.gateway:
        msg = "the boss must wait at the gateway so defeat is always possible"
        return [Problem(code="boss_not_at_gateway", message=msg, subject=graph.boss_lair)]
    return []


def _free_of_gateway(graph: RegionGraph) -> set[str]:
    """Nodes reachable from the arrival ignoring locks and never passing through the gateway."""
    seen = {graph.arrival}
    queue = deque([graph.arrival])
    while queue:
        node = queue.popleft()
        for edge in graph.edges:
            if edge.src == node and edge.dst != graph.gateway and edge.dst not in seen:
                seen.add(edge.dst)
                queue.append(edge.dst)
    return seen


def _can_reach(moves: dict[State, list[State]], goal: Iterable[State]) -> set[State]:
    """States from which a goal state is reachable (reverse search)."""
    back: dict[State, list[State]] = {}
    for src, dsts in moves.items():
        for dst in dsts:
            back.setdefault(dst, []).append(src)
    good = set(goal)
    queue = deque(good)
    while queue:
        for prev in back.get(queue.popleft(), ()):
            if prev not in good:
                good.add(prev)
                queue.append(prev)
    return good


def _progression(graph: RegionGraph) -> list[Problem]:
    out: list[Problem] = []
    states, moves = _explore(graph)
    reached = {node for node, _ in states}
    for node in graph.nodes:
        if node not in reached:
            msg = f"{node!r} cannot be reached from the arrival"
            out.append(Problem(code="unreachable_node", message=msg, subject=node))
    free = _free_of_gateway(graph)
    for spoke in graph.spokes:
        if spoke not in free:
            msg = f"spoke {spoke!r} can only be reached through the gateway"
            out.append(Problem(code="spoke_behind_gateway", message=msg, subject=spoke))
    at_gate = {s for s in states if s[0] == graph.gateway}
    if not at_gate:
        msg = "the gateway can never be entered (its lock cannot be satisfied)"
        out.append(Problem(code="gateway_unreachable", message=msg, subject=graph.gateway))
        return out
    stuck = sorted(states - _can_reach(moves, at_gate), key=lambda s: (s[0], sorted(s[1])))
    if stuck:
        node, visited = stuck[0]
        msg = f"soft-lock: from {node!r} (visited {sorted(visited)}) the gateway is unreachable"
        out.append(Problem(code="softlock", message=msg, subject=node))
    return out


def validate_region(graph: RegionGraph) -> list[Problem]:
    problems = _structure(graph) + _boss(graph)
    if not any(p.code in {"bad_shape", "unknown_node", "duplicate_node"} for p in problems):
        problems += _progression(graph)
    return problems


def validate_campaign_graph(graph: CampaignGraph) -> list[Problem]:
    problems = [p for region in graph.regions for p in validate_region(region)]
    pairs = list(zip(graph.regions, graph.regions[1:], strict=False))
    if len(graph.links) != len(pairs):
        msg = f"expected {len(pairs)} inter-act links, found {len(graph.links)}"
        problems.append(Problem(code="bad_link", message=msg))
        return problems
    for link, (a, b) in zip(graph.links, pairs, strict=True):
        if (link.src, link.dst, link.requires_resolved) != (a.gateway, b.arrival, (a.region_id,)):
            msg = (
                f"link {link.src}->{link.dst} must join {a.region_id}'s gateway to the next arrival"
            )
            problems.append(Problem(code="bad_link", message=msg, subject=link.src))
    return problems


def graph_neighbours(edges: Iterable[GraphEdge]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for edge in edges:
        out.setdefault(edge.src, [])
        out.setdefault(edge.dst, [])
        if edge.dst not in out[edge.src]:
            out[edge.src].append(edge.dst)
    return out


def locked_nodes_for(
    edges: Iterable[GraphEdge], visited: Collection[str], resolved: Collection[str] = ()
) -> list[str]:
    """Nodes the party cannot enter yet: no inbound edge is open AND starts at a visited node.

    The source must be visited so that a later region's own edges (spokes back to its arrival)
    do not unlock its arrival before the previous region is resolved.
    """
    inbound: dict[str, list[GraphEdge]] = {}
    for edge in edges:
        inbound.setdefault(edge.dst, []).append(edge)
    return [
        node
        for node, into in inbound.items()
        if not any(e.src in visited and _open(e, visited, resolved) for e in into)
    ]


def legal_neighbours(world: World, node: str | None) -> tuple[str, ...]:
    """Exits of `node` the party may take now: graph neighbours that are not locked."""
    if node is None:
        return ()
    return tuple(n for n in world.neighbours.get(node, ()) if n not in world.locked_nodes)


def travel_route(world: World, start: str | None, goal: str) -> tuple[str, ...] | None:
    """Shortest walk from `start` to `goal` over the exits open now (breadth first, exits in
    their stored order, so ties are deterministic)."""
    if start is None:
        return None
    came: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            path: list[str] = []
            step: str | None = node
            while step is not None and step != start:
                path.append(step)
                step = came[step]
            return tuple(reversed(path))
        for nxt in legal_neighbours(world, node):
            if nxt not in came:
                came[nxt] = node
                queue.append(nxt)
    return None
