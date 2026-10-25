"""Candidate rows of the typed-line corpus: weak labels for the labeller, not truth."""

from collections.abc import Iterator
from typing import Any

from scripts.interpret import lib

_QUIET = frozenset(
    {"action_declared", "narration_recorded", "fact_recorded", "scene_summarised", "dice_rolled"}
)
_ID_FIELDS = (
    "target_id",
    "spell_id",
    "item_id",
    "item",
    "option",
    "to_zone",
    "destination",
    "region_id",
    "creature_id",
    "actor_id",
    "attacker_id",
)
_MAX_ENGINE = 12


def _key(event: Any) -> str:
    for name in _ID_FIELDS:
        value = getattr(event, name, None)
        if isinstance(value, str) and value:
            return f"{event.type}:{value}"
    return str(event.type)


def engine_summary(line: lib.Line) -> list[str]:
    """Event types and key ids between this line and the next declared one."""
    found: list[str] = []
    for entry in line.log[line.index + 1 :]:
        if entry.event.type == "action_declared":
            break
        if entry.event.type not in _QUIET:
            found.append(_key(entry.event))
    return found[:_MAX_ENGINE]


def candidate(line: lib.Line) -> dict[str, Any]:
    actor = line.event.creature_id
    text = line.event.text
    try:
        menu = lib.menu_for(line.state, actor)
        scope: str | None = menu.scope.value
        ids = [e.id for e in menu.entries]
    except Exception:  # a state the menu cannot be built for is still a row
        scope, ids = None, []
    return {
        "id": line.id,
        "run": line.run,
        "seq": line.seq,
        "actor_id": actor,
        "text": text,
        "scope": scope,
        "menu_ids": ids,
        "engine": engine_summary(line),
    }


def candidates(runs: list[str]) -> Iterator[dict[str, Any]]:
    for run in runs:
        for line in lib.walk(run):
            yield candidate(line)
