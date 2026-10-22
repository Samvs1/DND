"""Light and usable gear in the scene manifest (M27.5), built only through THE context builder
(`aidm.dm.context.build_context`, which places these lines before the closed-world statement).

- `light_lines(state)`: for every purpose: whether this place is dark, which carried lights
  light it, and whether foes here are alerted (they cannot be surprised).
- `gear_lines(state, scene, show_ids)`: for the adjudicator: the uses of each present hero's
  carried gear that fit here now (`aidm.rules.item_use.usable_uses`), e.g.
  "Usable gear of Brak [fighter]: Torch [torch]: light this dark place", so the model calls
  `use_item` instead of granting advantage itself.

Public API: `light_lines(state) -> list[str]`, `gear_lines(state, scene, show_ids) -> list[str]`.
"""

from aidm.models.state import GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.item_use import usable_uses
from aidm.rules.light import place_dark
from aidm.rules.scene import SceneView


def _tag(show_ids: bool, ident: str) -> str:
    return f" [{ident}]" if show_ids else ""


def light_lines(state: GameState) -> list[str]:
    world = state.world
    lines: list[str] = []
    if place_dark(state):
        lights = [
            f"{state.creatures[x.creature_id].name}'s {gear_name(x.item).lower()}"
            for x in world.lights
            if x.creature_id in state.creatures
        ]
        lit = f"lit by {', '.join(lights)}" if lights else "unlit: searching here is hard"
        lines.append(f"Light: this place is dark, {lit}")
    if world.alerted is not None and world.alerted == world.current_node:
        why = "a light gave the party away" if world.alerted_by == "light" else "noise"
        lines.append(f"Alerted: foes here cannot be surprised ({why})")
    return lines


def gear_lines(state: GameState, scene: SceneView, show_ids: bool) -> list[str]:
    lines: list[str] = []
    for cid in scene.party_ids:
        parts: list[str] = []
        for item, use, target in usable_uses(state, cid):
            feature = state.world.features.get(target or "")
            on = f" on {feature.name}{_tag(show_ids, feature.id)}" if feature is not None else ""
            parts.append(f"{gear_name(item)}{_tag(show_ids, item)}{on}: {use.label.lower()}")
        if parts:
            who = state.creatures[cid].name + _tag(show_ids, cid)
            lines.append(f"Usable gear of {who}: {'; '.join(dict.fromkeys(parts))}")
    return lines
