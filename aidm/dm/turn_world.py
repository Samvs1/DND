"""World truth of a turn beyond fights: place, lights, things picked up (M29.7b, R2 R12 R17).

Round 2: routed travel stopped one place short (a quest ask, an offer, or simply the first leg)
while the prose told arrival at the destination; a vial and a chime were told filled and lifted
from the dust with no event; a burning torch "will not come" and a candle went out with no event.
From the events already applied to `state`:
- `destination(state, text)`: the map place the player's travel words name (its display name);
  `short_of(state, events, text)`: that place when the party moved this turn but stands
  elsewhere (one leg of the route), else "";
- `burning(state)`: light noun -> who carries that burning light ("torch" -> "Rook");
- `picked_up(events)`: whether any event put a thing into a hero's hands (found, lifted, gained);
- `travel_text(text, events)`: the player's words, or those of the turn's `ActionDeclared`.

Public API: `TRAVEL`, `destination`, `short_of`, `burning`, `picked_up`, `travel_text`.
"""

import re
from collections.abc import Sequence

from aidm.data.guard_lexicon import guard_lexicon
from aidm.dm.entities import display_name
from aidm.dm.guard_text import plain
from aidm.models import events as ev
from aidm.models import world_events as we
from aidm.models.quest_events import KeepsakeTaken
from aidm.models.state import GameState

TRAVEL = re.compile(
    r"\b(?:go|goes|travel|travels|head|heads|walk|walks|journey|journeys|ride|rides)"
    r"(?: back)? (?:to|towards?|into|for) (?:the )?(?P<dest>[a-z0-9' -]{3,})"
)
_PICKED = (we.ItemRemoved, we.ItemDiscovered, we.KeepsakeGained, KeepsakeTaken)


def _bare(name: str) -> str:
    low = plain(name).casefold().strip()
    return low.removeprefix("the ").strip()


def travel_text(text: str | None, events: Sequence[ev.AnyEvent]) -> str:
    if text:
        return text
    said = [e.text for e in events if isinstance(e, we.ActionDeclared)]
    return said[-1] if said else ""


def destination(state: GameState, text: str) -> tuple[str, str] | None:
    """(node id, display name) of the known place the travel words name, if any."""
    m = TRAVEL.search(plain(text).casefold())
    if m is None:
        return None
    dest = m.group("dest").strip().rstrip(".!")
    for node, name in sorted(state.world.node_names.items()):
        bare = _bare(name)
        if len(bare) >= 4 and (dest.startswith(bare) or bare.startswith(dest)):
            return node, name
    return None


def short_of(state: GameState, events: Sequence[ev.AnyEvent], text: str | None) -> str:
    if not any(isinstance(e, we.PartyMoved) for e in events):
        return ""
    found = destination(state, travel_text(text, events))
    if found is None or found[0] == state.world.current_node:
        return ""
    return found[1]


def burning(state: GameState) -> dict[str, str]:
    lex = guard_lexicon()
    out: dict[str, str] = {}
    for light in state.world.lights:
        bearer = state.creatures.get(light.creature_id)
        words = set(re.findall(r"[a-z]+", display_name(light.item).casefold()))
        for noun in words & lex.light_nouns:
            out.setdefault(noun, bearer.name if bearer is not None else light.creature_id)
    return out


def picked_up(events: Sequence[ev.AnyEvent]) -> bool:
    return any(
        isinstance(e, _PICKED) or (isinstance(e, ev.InventoryChanged) and e.delta > 0)
        for e in events
    )
