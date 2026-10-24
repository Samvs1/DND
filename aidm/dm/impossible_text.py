"""The lines of an impossible action (M30.1, docs/next/GOAL_IMPOSSIBLE.md).

`IMPOSSIBLE_EVENT_LINES` join `aidm.dm.event_text` (the authoritative fact the context builder
lists for the narrator; public too, so facts only); `IMPOSSIBLE_EVENT_NOTES` are the model-only
instruction to tell the attempt failing, never working; `IMPOSSIBLE_TEMPLATE_LINES` join
`aidm.dm.narration_templates` (the player's line when no model is available, and the guard's safe
fallback). No line names a number: nothing was rolled.

Public API: `IMPOSSIBLE_EVENT_LINES`, `IMPOSSIBLE_EVENT_NOTES`, `IMPOSSIBLE_TEMPLATE_LINES`,
`IMPOSSIBLE_NOTE`.
"""

from collections.abc import Callable
from typing import Any

from aidm.dm.entities import display_name
from aidm.models.impossible import ActionImpossible
from aidm.models.state import GameState

IMPOSSIBLE_NOTE = (
    "{who}'s attempt cannot work ({reason}). No dice were rolled. Tell it failing or never"
    " getting started, in the fiction; never tell it working, partly working or done."
)


def _who(state: GameState, creature_id: str) -> str:
    creature = state.creatures.get(creature_id)
    return creature.name if creature is not None else display_name(creature_id)


def _reason(event: ActionImpossible) -> str:
    return event.reason.strip().rstrip(".")


def _fact(state: GameState, e: ActionImpossible) -> str:
    return f"{_who(state, e.creature_id)} cannot do that: {_reason(e)}."


def _note(state: GameState, e: ActionImpossible) -> str:
    return IMPOSSIBLE_NOTE.format(who=_who(state, e.creature_id), reason=_reason(e))


def _story(state: GameState, e: ActionImpossible) -> str:
    return f"{_who(state, e.creature_id)} tries, but it cannot be done: {_reason(e)}."


IMPOSSIBLE_EVENT_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    ActionImpossible: _fact,
}

IMPOSSIBLE_EVENT_NOTES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    ActionImpossible: _note,
}

IMPOSSIBLE_TEMPLATE_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    ActionImpossible: _story,
}
