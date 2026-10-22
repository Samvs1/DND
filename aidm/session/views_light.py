"""Light, darkness, boons and locks on the public views (M27.8, docs/next/GOAL_ITEMS.md "What
players see"): the extra fields of `PublicCreature`, `PublicZone`, `PublicScene` and
`PublicFeature`. Derived from state on every projection, never stored.

Public API: `hero_extras(state, creature) -> dict`, `zone_extras(state, zone_id) -> dict`,
`lock_tier(feature) -> str`.
"""

from typing import Any

from aidm.models.protocol_views import PublicBoon
from aidm.models.state import Creature, GameState
from aidm.models.world import ActiveBoon, WorldFeature
from aidm.rules.boons import hero_boons
from aidm.rules.item_effects import gear_name
from aidm.rules.light import (
    hero_light,
    light_reach_zones,
    lit_zones,
    node_dark,
    place_dark,
    place_light,
)


def _boon(boon: ActiveBoon) -> PublicBoon:
    skills = (s.replace("_", " ").title() for s in boon.skills)
    saves = (f"{s.title()} saves" for s in boon.saves_against)
    return PublicBoon(name=boon.name, helps=(*skills, *saves))


def hero_extras(state: GameState, creature: Creature) -> dict[str, Any]:
    if creature.pc is None:
        return {}
    light = hero_light(state, creature.id)
    return {
        "darkvision": creature.darkvision,
        "light": gear_name(light.item) if light is not None else "",
        "boons": tuple(_boon(b) for b in hero_boons(state, creature.id)),
    }


def zone_extras(state: GameState, zone_id: str) -> dict[str, Any]:
    dark = place_dark(state)
    if not dark:
        return {}
    bearers = tuple(
        light.creature_id
        for light in state.world.lights
        if zone_id in light_reach_zones(state, light.creature_id, light.reach)
    )
    return {"dark": True, "lit": zone_id in lit_zones(state), "lit_by": bearers}


def place_lit_name(state: GameState, node_id: str) -> str:
    """M27.11: "Torch" when the place is dark and a hero carries a light here, else ""."""
    light = place_light(state)
    if light is None or not node_dark(state, node_id):
        return ""
    return gear_name(light.item)


def lock_tier(feature: WorldFeature) -> str:
    return feature.lock.dc_tier.value if feature.lock is not None else ""
