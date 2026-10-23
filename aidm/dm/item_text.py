"""Engine lines of the gear events (M27.5; merged into `aidm.dm.event_text`, so the public feed,
the narrator's event list and the template narration all read the same words).

- `LightLit` in a dark place: who lit what, then the light-versus-stealth warning
  (`LIGHT_WARNING`), once per lighting (arriving with a light already lit adds no line).
- `LightEnded` put out ("doused"): who put out which light; other ends have no line.
- `ItemUsed`: who used which gear (a light's own line says it for a light; M27.6: a use that
  changed nothing says "no special effect").
- `FeatureUnlocked`: the lock is open, and how; no line ever opens a lock without this event.
- `HandedOver` (M29.7a R8): who handed what (an item, a keepsake or gold) to which hero.
- `PlaceAlerted` by noise (M27.11: forcing a lock, a noisy use; the event fires once per place):
  `NOISE_WARNING`. A light's alert has no line of its own (`LIGHT_WARNING` says it).
- `encounter_line(state)`: the fight-start line, plus `DARK_FIGHT` in a dark place (M27.8), plus
  `SEEN_LIGHT` when the alert of this place
  came from a light (`World.alerted_by`).
Refusals, boons, alerts and charting have no line (the refusal is for the model only).

Public API: `LIGHT_WARNING`, `NOISE_WARNING`, `SEEN_LIGHT`, `DARK_FIGHT`, `ITEM_EVENT_LINES`,
`encounter_line(state, event)`.
"""

from collections.abc import Callable
from typing import Any

from aidm.data.item_uses import LightPlace, uses_for_item
from aidm.models.encounter_events import EncounterStarted
from aidm.models.item_events import (
    FeatureUnlocked,
    HandedOver,
    ItemUsed,
    LightEnded,
    LightLit,
    PlaceAlerted,
)
from aidm.models.state import GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.light import DOUSED, place_dark

LIGHT_WARNING = "Your light shows you the way, and shows you to anything waiting here."
SEEN_LIGHT = "They saw your light coming. No surprise."
NOISE_WARNING = "The noise carries. Anything nearby is warned."
FIGHT_STARTS = "A fight breaks out."
DARK_FIGHT = "It is dark here. Heroes without darkvision attack into dark zones at disadvantage."


def _who(state: GameState, creature_id: str) -> str:
    creature = state.creatures.get(creature_id)
    if creature is not None:
        return creature.name
    npc = state.world.npcs.get(creature_id)  # M29.9a: gold paid to an NPC
    return npc.name if npc is not None else "someone"


def _lit(state: GameState, e: LightLit) -> str:
    line = f"{_who(state, e.creature_id)} lights a {gear_name(e.item).lower()}."
    return f"{line} {LIGHT_WARNING}" if place_dark(state) else line


def _ended(state: GameState, e: LightEnded) -> str | None:
    if e.reason != DOUSED:
        return None
    what = gear_name(e.item).lower() if e.item else "light"
    return f"{_who(state, e.creature_id)} puts out the {what}."


def _used(state: GameState, e: ItemUsed) -> str | None:
    use = next((u for u in uses_for_item(e.item) if u.id == e.use_id), None)
    if use is not None and isinstance(use.effect, LightPlace):
        return None
    used = f"{_who(state, e.creature_id)} uses the {gear_name(e.item).lower()}"
    return f"{used}: no special effect." if e.no_effect else f"{used}."


def _unlocked(state: GameState, e: FeatureUnlocked) -> str:
    feature = state.world.features.get(e.feature_id)
    name = feature.name if feature is not None else "the lock"
    how = {"key": "unlocks", "pick": "picks the lock of", "force": "forces open"}[e.method]
    return f"{_who(state, e.creature_id)} {how} {name}."


def _handed(state: GameState, e: HandedOver) -> str:
    taker = _who(state, e.to_id)
    if e.gold:
        what = f"{e.gold} gold"
    elif e.item is not None:
        name = gear_name(e.item).lower()
        what = f"{e.qty} x {name}" if e.qty > 1 else f"the {name}"
    else:
        held = [
            k
            for cid in (e.creature_id, e.to_id)
            if (hero := state.creatures.get(cid)) is not None and hero.pc is not None
            for k in hero.pc.keepsakes
        ]
        what = f"the {next((k.name for k in held if k.id == e.keepsake_id), 'keepsake')}"
    return f"{_who(state, e.creature_id)} hands {what} to {taker}."


def _alerted(state: GameState, e: PlaceAlerted) -> str | None:
    return NOISE_WARNING if e.reason == "noise" else None  # once per place: the event is


def encounter_line(state: GameState, event: EncounterStarted) -> str:
    world = state.world
    seen = world.alerted_by == "light" and world.alerted == world.current_node
    parts = [FIGHT_STARTS]
    if place_dark(state):
        parts.append(DARK_FIGHT)  # M27.8: darkness is never hidden
    if seen:
        parts.append(SEEN_LIGHT)
    return " ".join(parts)


ITEM_EVENT_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    LightLit: _lit,
    LightEnded: _ended,
    ItemUsed: _used,
    FeatureUnlocked: _unlocked,
    PlaceAlerted: _alerted,
    HandedOver: _handed,
    EncounterStarted: encounter_line,
}
