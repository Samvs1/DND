"""The deterministic description of where the party stands (M36.1, moved out of
`aidm.dm.scene_intent`): the place, its description, the people here, hostiles, features, items
lying here and the ways on (a locked way with its short reason).

Public API: `look_around_text(state) -> str`.
"""

from aidm.models.state import GameState
from aidm.rules.gateway_lock import short_reason
from aidm.rules.scene import current_scene, node_display_name


def _listing(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def look_around_text(state: GameState) -> str:
    scene = current_scene(state)
    world = state.world
    parts = [f"You are at {scene.node_name}."]
    if scene.description:
        parts.append(scene.description.strip())
    npcs = [world.npcs[i] for i in scene.npc_ids]
    people = [f"{n.name} ({n.role})" if n.role else n.name for n in npcs]
    parts.append(f"Here with you: {_listing(people)}." if people else "Nobody else is here.")
    foes = [state.creatures[c].name for c in scene.monster_ids]
    if foes:
        parts.append(f"Hostile: {_listing(foes)}.")
    features = [world.features[f].name for f in scene.feature_ids]
    if features:
        parts.append(f"You notice: {_listing(features)}.")
    items = [world.items[i].name for i in scene.item_ids]
    if items:
        parts.append(f"Lying here: {_listing(items)}.")
    exits = [
        node_display_name(state, e)
        + (f" ({short_reason(state, e)})" if e in scene.locked_exits else "")
        for e in scene.exits
    ]
    parts.append(f"Ways on: {_listing(exits)}." if exits else "There is no obvious way on.")
    return " ".join(parts)
