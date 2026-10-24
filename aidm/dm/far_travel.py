"""Typed travel to a place further than the next road (M32.1a X6, round 5: "We make our way back
to Hollowgate Cross, then on to the Barrow of the Hollow King" and "we head back to Bramble
Pike's stall at the Briar Vein" stopped at the first place while the story told the whole way;
"I travel to The Skiff-Road", two roads away, got the stock filler line and no reason).

`far_route(state, dest)`: the place the words name last (every word of its name, "the Briar
Vein" in "Bramble Pike's stall at the Briar Vein") is the goal; the route is the shortest walk
over the roads open now (`rules.world_graph.travel_route`), so "A, then on to B" goes by A
when A is on the way. A goal with no open road gets the plain `NO_ROAD` line. The travel vote
then walks it hop by hop (`session.scene_votes`).

Public API: `NO_ROAD`, `far_route(state, dest) -> tuple[str, ...] | str | None` (the route's
nodes, the plain reason, or None when the words name no other place).
"""

import re

from aidm.models.state import GameState
from aidm.rules.scene import node_display_name
from aidm.rules.world_graph import travel_route

NO_ROAD = "No open road you know leads from here to {place}."
_DROP = frozenset({"the", "of", "a", "an"})


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower().replace("'s", ""))


def _said_at(words: list[str], name: str) -> int | None:
    want = [w for w in _tokens(name) if w not in _DROP]
    if not want or not set(want) <= set(words):
        return None
    return max(words.index(w) for w in want)


def _goal(state: GameState, dest: str) -> str | None:
    world = state.world
    nodes = set(world.neighbours) | {n for exits in world.neighbours.values() for n in exits}
    words = _tokens(dest)
    said = [
        (at, node)
        for node in sorted(nodes)
        if (at := _said_at(words, node_display_name(state, node))) is not None
    ]
    return max(said)[1] if said else None


def far_route(state: GameState, dest: str) -> tuple[str, ...] | str | None:
    goal = _goal(state, dest)
    here = state.world.current_node
    if goal is None or goal == here:
        return None
    route = travel_route(state.world, here, goal)
    return route if route else NO_ROAD.format(place=node_display_name(state, goal))
