"""The lines of a spell cast at the scene (M30.2b: no free spells by typing).

Out of a fight, a spell aimed at no creature is cast at the scene (`SpellCast.at_scene`,
`rules.spells.scene_cast`): the slot or resource is spent and the engine records nothing else.
The narrator is told so from the event, in plain words built from the spell's effect data
(`SCENE_LIMITS`, by effect type, never by spell): a teleport carries no one to another place
(travel is still travel), a surface leaves nothing lasting, a hostile effect strikes no one.

`CAST_EVENT_LINES` join `aidm.dm.event_text` (the public fact; a cast with targets or a zone
renders None, as before: its effects tell it), `CAST_EVENT_NOTES` the model-only instruction
(tell the casting, no other effect), `CAST_TEMPLATE_LINES` join `aidm.dm.narration_templates`.

Public API: `CAST_EVENT_LINES`, `CAST_EVENT_NOTES`, `CAST_TEMPLATE_LINES`, `SCENE_LIMITS`,
`SCENE_NOTE`, `scene_limits(spell_id)`.
"""

from collections.abc import Callable
from typing import Any

from aidm.data.combat_data import combat_registries
from aidm.dm.entities import display_name
from aidm.models.combat_events import SpellCast
from aidm.models.state import GameState

_STRIKES = "it strikes no one"
SCENE_LIMITS: dict[str, str] = {
    "teleport": "it carries no one to another place",
    "surface": "nothing it makes lasts beyond this moment",
    "attack_roll": _STRIKES,
    "save": _STRIKES,
    "damage": _STRIKES,
    "hp_pool": _STRIKES,
    "multi_target": _STRIKES,
}
_NOTHING = "it changes nothing that lasts"
SCENE_NOTE = (
    "{who} cast {spell} here, outside a fight, and the spell is spent: {limits}. Tell the casting"
    " and how it looks in this place; tell no other effect, and no one moved to another place."
)


def scene_limits(spell_id: str) -> str:
    """The plain words of what a scene cast of this spell cannot do, from its effect types."""
    spell = combat_registries().spells.find(spell_id)
    kinds = [e.type for e in spell.effects] if spell is not None else []
    words = list(dict.fromkeys(SCENE_LIMITS[k] for k in kinds if k in SCENE_LIMITS))
    return " and ".join(words) if words else _NOTHING


def _who(state: GameState, creature_id: str) -> str:
    creature = state.creatures.get(creature_id)
    return creature.name if creature is not None else display_name(creature_id)


def _fact(state: GameState, e: SpellCast) -> str | None:
    if not e.at_scene:
        return None
    spell = display_name(e.spell_id)
    return (
        f"{_who(state, e.caster_id)} casts {spell} (outside a fight: {scene_limits(e.spell_id)})."
    )


def _note(state: GameState, e: SpellCast) -> str | None:
    if not e.at_scene:
        return None
    who, spell = _who(state, e.caster_id), display_name(e.spell_id)
    return SCENE_NOTE.format(who=who, spell=spell, limits=scene_limits(e.spell_id))


def _story(state: GameState, e: SpellCast) -> str:
    cast = f"{_who(state, e.caster_id)} casts {display_name(e.spell_id)}"
    return f"{cast}, but {scene_limits(e.spell_id)}." if e.at_scene else f"{cast}."


CAST_EVENT_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {SpellCast: _fact}
CAST_EVENT_NOTES: dict[type[Any], Callable[[GameState, Any], str | None]] = {SpellCast: _note}
CAST_TEMPLATE_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {SpellCast: _story}
