"""A turn that changed nothing because the engine refused it, said plainly (M32.1a X7, round 5:
"Rook steps forward and gives Caul's Bait-Cache to Abbess Marwen Salt" and "I travel to The
Skiff-Road" were told only "The moment passes, and the world waits for what you do next.").

`refusal_line(state, errors)`: the first refused tool call's reason as one player-facing line
("That does not happen: the way on is shut."), any "; ..." model hint cut and every quoted id
read as the name of what it names in the world (a place, a person, a creature, an item), else as
"that" (an id the world does not know is never told as a name). A reason written for the model
(numbers, ids, schema words) is not told: the line then says nothing here allows it. None when
nothing was refused.
The narrator hands it to the template narration as the turn's notice, so a turn with no events
that fell back to the template says why instead of the stock filler line.

Public API: `NOT_DONE`, `NOTHING_ALLOWS`, `refusal_line(state, errors) -> str | None`.
"""

import re
from collections.abc import Iterable

from aidm.models.state import GameState
from aidm.rules.scene import node_display_name

NOT_DONE = "That does not happen: {why}."
NOTHING_ALLOWS = "nothing here allows it"
_ID = re.compile(r"'([a-z0-9][a-z0-9_-]*)'")
_PLAIN = re.compile(  # a reason meant for the model (numbers, ids, schema words) is not told
    r"\d|catalog|unknown|invalid|argument|\bids?\b|allowed|\bcap\b|\btags?\b|archetype"
    r"|needs exactly|must be one of|at most|registers|refer to"
)


def _name(state: GameState, key: str) -> str:
    world = state.world
    if key in world.node_names or key in world.neighbours:
        return node_display_name(state, key)
    for found in (world.npcs.get(key), state.creatures.get(key), world.items.get(key)):
        if found is not None:
            return found.name
    return "that"


def refusal_line(state: GameState, errors: Iterable[str]) -> str | None:
    said = [e for e in errors if e.strip()]
    for error in said:
        why = _ID.sub(lambda m: _name(state, m.group(1)), error.split(";")[0]).strip(" .")
        if why and _PLAIN.search(why) is None:
            return NOT_DONE.format(why=why)
    return NOT_DONE.format(why=NOTHING_ALLOWS) if said else None
