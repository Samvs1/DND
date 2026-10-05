"""Region graph properties (M5.2): the boss at the gateway is never a soft-lock."""

from __future__ import annotations

from collections import deque

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.rules.world_graph import build_region_graph, legal_neighbours, validate_region
from tests.unit.rules.graph_fixtures import region_plan, world_at

type Walk = tuple[str, frozenset[str]]


def _reachable(start: Walk, step: dict[Walk, list[Walk]]) -> set[Walk]:
    seen = {start}
    queue = deque([start])
    while queue:
        for nxt in step.get(queue.popleft(), ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


@settings(max_examples=120, deadline=None)
@given(spokes=st.integers(2, 3), seed=st.integers(0, 10_000), region=st.integers(1, 99))
def test_v1_unreachable_boss_never_softlocks(spokes: int, seed: int, region: int) -> None:
    graph = build_region_graph(region_plan(spokes, f"r{region}"), seed)
    assert validate_region(graph) == []
    start: Walk = (graph.arrival, frozenset({graph.arrival}))
    step: dict[Walk, list[Walk]] = {}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        if state in step:
            continue
        node, visited = state
        world = world_at(graph, node, visited)
        step[state] = [(n, visited | {n}) for n in legal_neighbours(world, node)]
        queue.extend(step[state])
    # the gateway is only ever entered with every spoke visited
    for node, visited in step:
        if node == graph.gateway:
            assert set(graph.spokes) <= visited
    # from EVERY reachable state, the gateway (the boss, always defeatable there) is reachable
    for state in step:
        assert any(n == graph.gateway for n, _ in _reachable(state, step)), state
    # and every node is visitable
    assert {n for n, _ in step} == set(graph.nodes)
