"""Light and darkness (docs/next/GOAL_ITEMS.md "Light and darkness", M27.2; carried, M27.12).

PURE and derived. Nothing is stored per zone and darkness is never stored at all:
- A place is dark when one of its known terrains is: a terrain tag of the place plan
  (`aidm.rules.zone_gen.known_terrains`, the terrains its fight maps are drawn from) has
  `dark: true` in data/bg3/zone_templates.json (cave, crypt), so a crypt among ruins is dark.
  A place without a plan is never dark, so old saves need nothing.
- A light is CARRIED (`World.lights`, one `CarriedLight` per hero, set by `LightLit`): it stays
  lit and travels with its bearer from place to place until the next long rest
  (`LightEnded`, `aidm.rules.boons.long_rest_light_events`). Out of a fight a dark place is lit
  while a bearer is with the party (the party moves together).
- In a fight light is per zone: a zone of a dark place is lit when a bearer stands in it or,
  for a "touching" light (torch, lantern: 20 ft of bright light covers the next 15 ft hop,
  SRD), in a touching zone; a "zone" light (candle) lights its own zone only. Every bearer
  lights. A surface whose data says `lights` (fire) lights its zone. A light moves with its
  bearer (read from the bearer's current zone); a downed or dead bearer's light stays in their
  zone, a bearer who left the fight takes it along.
- Arriving in a dark place while a living hero carries a light gives the party away
  (`PlaceAlerted`), and a dead bearer's light ends when the party moves on (`arrival_events`).
- Darkness only ever adds disadvantage. It never hides a quest item or a passage.

Public API:
- `DARKNESS`: the advantage reason ("Darkness") shown with the dice (`adv_why`).
- `node_dark(state, node) -> bool`, `place_dark(state) -> bool`: the place is dark by terrain.
- `hero_light(state, creature_id) -> CarriedLight | None`: the light that hero carries.
- `place_light(state) -> CarriedLight | None`: the first light a hero of the party carries.
- `light_reach_zones(state, creature_id, reach) -> frozenset[str]`: the zones a light of
  `reach` carried by that combatant lights in the active fight (empty without one).
- `lit_zones(state) -> frozenset[str]`: the lit zones of the active fight's map (every zone
  when the place is not dark; empty without an active fight).
- `zone_lit(state, zone_id) -> bool`: in a fight, the zone is lit (above); out of a fight the
  place is not dark, or a light is carried.
- `sight_darkness(state, what) -> tuple[str, ...]`: (`DARKNESS`,) for a sight or search check
  (`aidm.rules.scene.is_search_check`) out of a fight in a dark unlit place, for everyone
  (darkvision sees darkness as dim light, still disadvantage on Perception: SRD); else ().
- `attack_darkness(state, attacker_id, target_zone) -> int`: 1 disadvantage source when a hero
  without darkvision attacks a target standing in a dark unlit zone; monsters see (0).
- `arrival_events(state, to_node) -> list[AnyEvent]`: what carried light does when the party
  arrives at `to_node` (emit right AFTER its `PartyMoved`, which clears the old alert).
"""

from aidm.data.surface_defs import surface_defs
from aidm.data.zone_templates import zone_templates
from aidm.models.abilities import Ability, Skill
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.item_events import LightEnded, PlaceAlerted
from aidm.models.state import GameState
from aidm.models.world import CarriedLight, LightReach
from aidm.rules.progression import node_plan
from aidm.rules.scene import is_search_check
from aidm.rules.zone_gen import known_terrains
from aidm.rules.zones import zone_neighbors

DARKNESS = "Darkness"


def _active(state: GameState) -> Encounter | None:
    enc = state.encounter
    return enc if enc is not None and enc.status is EncounterStatus.ACTIVE else None


def node_dark(state: GameState, node: str | None) -> bool:
    plan = node_plan(state, node)
    if plan is None:
        return False
    return any(t.dark for t in known_terrains(plan.terrain_tags, zone_templates()))


def place_dark(state: GameState) -> bool:
    return node_dark(state, state.world.current_node)


def hero_light(state: GameState, creature_id: str) -> CarriedLight | None:
    return next((x for x in state.world.lights if x.creature_id == creature_id), None)


def place_light(state: GameState) -> CarriedLight | None:
    return next((x for x in state.world.lights if x.creature_id in state.creatures), None)


def _surface_lights(kind: str) -> bool:
    found = surface_defs().find(kind)
    return found is not None and found.lights


def _reach_zones(enc: Encounter, creature_id: str, reach: LightReach) -> frozenset[str]:
    bearer = enc.combatants.get(creature_id)
    if bearer is None or bearer.withdrawn is not None:
        return frozenset()
    zones = {bearer.zone_id}
    if reach == "touching":
        zones.update(other for other, _ in zone_neighbors(enc.zone_map, bearer.zone_id))
    return frozenset(zones)


def light_reach_zones(state: GameState, creature_id: str, reach: LightReach) -> frozenset[str]:
    enc = _active(state)
    return _reach_zones(enc, creature_id, reach) if enc is not None else frozenset()


def _fight_lit_zones(state: GameState, enc: Encounter) -> frozenset[str]:
    zmap = enc.zone_map
    lit = {z.id for z in zmap.zones if any(_surface_lights(s.kind) for s in z.surfaces)}
    for light in state.world.lights:
        lit.update(_reach_zones(enc, light.creature_id, light.reach))
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


def arrival_events(state: GameState, to_node: str) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    living = False
    for light in state.world.lights:
        bearer = state.creatures.get(light.creature_id)
        if bearer is None or bearer.dead:
            events.append(LightEnded(creature_id=light.creature_id, reason="left behind"))
        else:
            living = True
    if living and node_dark(state, to_node):
        events.append(PlaceAlerted(node=to_node))
    return events
