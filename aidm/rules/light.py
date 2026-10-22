"""Light and darkness (docs/next/GOAL_ITEMS.md "Light and darkness", M27.2). PURE and derived.

Nothing is stored per zone and darkness is never stored at all:
- A place is dark when one of its known terrains is: a terrain tag of the place plan
  (`aidm.rules.zone_gen.known_terrains`, the terrains its fight maps are drawn from) has
  `dark: true` in data/bg3/zone_templates.json (cave, crypt), so a crypt among ruins is dark.
  A place without a plan is never dark, so old saves need nothing.
- `World.lit` (`PlaceLit`, cleared by the reducer on `PartyMoved`) is the light a hero carries
  in the current place. Out of a fight it lights the whole place.
- In a fight light is per zone: a zone of a dark place is lit when the bearer of the place's
  light stands in it or, for a "touching" light (torch, lantern: 20 ft of bright light covers
  the next 15 ft hop, SRD), in a touching zone; a "zone" light (candle) lights its own zone
  only. A surface whose data says `lights` (fire) lights its zone. The light moves with its
  bearer (read from the bearer's current zone); a bearer who left the fight takes it along.
- Darkness only ever adds disadvantage. It never hides a quest item or a passage.

Public API:
- `DARKNESS`: the advantage reason ("Darkness") shown with the dice (`adv_why`).
- `place_dark(state) -> bool`: the current place is dark by its terrain.
- `place_light(state) -> PlaceLight | None`: `World.lit` when it lights the current place.
- `lit_zones(state) -> frozenset[str]`: the lit zones of the active fight's map (every zone
  when the place is not dark; empty without an active fight).
- `zone_lit(state, zone_id) -> bool`: in a fight, the zone is lit (above); out of a fight the
  place is not dark, or it is lit.
- `sight_darkness(state, what) -> tuple[str, ...]`: (`DARKNESS`,) for a sight or search check
  (`aidm.rules.scene.is_search_check`) out of a fight in a dark unlit place, for everyone
  (darkvision sees darkness as dim light, still disadvantage on Perception: SRD); else ().
- `attack_darkness(state, attacker_id, target_zone) -> int`: 1 disadvantage source when a hero
  without darkvision attacks a target standing in a dark unlit zone; monsters see (0).
"""

from aidm.data.surface_defs import surface_defs
from aidm.data.zone_templates import zone_templates
from aidm.models.abilities import Ability, Skill
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.state import GameState
from aidm.models.world import PlaceLight
from aidm.rules.progression import node_plan
from aidm.rules.scene import is_search_check
from aidm.rules.zone_gen import known_terrains
from aidm.rules.zones import zone_neighbors

DARKNESS = "Darkness"


def _active(state: GameState) -> Encounter | None:
    enc = state.encounter
    return enc if enc is not None and enc.status is EncounterStatus.ACTIVE else None


def place_dark(state: GameState) -> bool:
    plan = node_plan(state, state.world.current_node)
    if plan is None:
        return False
    return any(t.dark for t in known_terrains(plan.terrain_tags, zone_templates()))


def place_light(state: GameState) -> PlaceLight | None:
    lit = state.world.lit
    return lit if lit is not None and lit.node == state.world.current_node else None


def _surface_lights(kind: str) -> bool:
    found = surface_defs().find(kind)
    return found is not None and found.lights


def _fight_lit_zones(state: GameState, enc: Encounter) -> frozenset[str]:
    zmap = enc.zone_map
    lit = {z.id for z in zmap.zones if any(_surface_lights(s.kind) for s in z.surfaces)}
    light = place_light(state)
    bearer = enc.combatants.get(light.by) if light is not None else None
    if light is not None and bearer is not None and bearer.withdrawn is None:
        lit.add(bearer.zone_id)
        if light.reach == "touching":
            lit.update(other for other, _ in zone_neighbors(zmap, bearer.zone_id))
    return frozenset(lit)


def lit_zones(state: GameState) -> frozenset[str]:
    enc = _active(state)
    if enc is None:
        return frozenset()
    if not place_dark(state):
        return frozenset(z.id for z in enc.zone_map.zones)
    return _fight_lit_zones(state, enc)


def zone_lit(state: GameState, zone_id: str) -> bool:
    if not place_dark(state):
        return True
    enc = _active(state)
    if enc is None:
        return place_light(state) is not None
    return zone_id in _fight_lit_zones(state, enc)


def sight_darkness(state: GameState, what: Skill | Ability) -> tuple[str, ...]:
    if _active(state) is not None or not is_search_check(what):
        return ()
    if not place_dark(state) or place_light(state) is not None:
        return ()
    return (DARKNESS,)


def attack_darkness(state: GameState, attacker_id: str, target_zone: str) -> int:
    attacker = state.creatures[attacker_id]
    if attacker.pc is None or attacker.darkvision > 0:
        return 0
    return 0 if zone_lit(state, target_zone) else 1
