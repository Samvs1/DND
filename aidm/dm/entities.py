"""The entity name registry: every name the world knows (SPEC 2.2 closed world, 6.5).

ONE place that answers "is this a known name?" for the guard (M4.6) and the context builder.
Names come from state only: party members, registered NPCs, creatures (living and dead),
features (visible ones in `visible`), world items, carried items, places and the lore
allow-list of the world bible (`World.lore_names`).

Public API:
- `display_name(index) -> str`: a readable name for an SRD index ("chain-mail" -> "Chain Mail").
- `EntityRegistry(party, npcs, monsters, dead, features, hidden_features, items, places, lore)`:
  frozensets of display names. `visible_names` is everything the narrator may name in the
  current scene's world (party, NPCs, living creatures, visible features, items, places, lore);
  `all_names` adds dead creatures and hidden features; `is_known(name)` is a case-insensitive
  lookup in `visible_names`.
- `entity_registry(state) -> EntityRegistry`.
"""

from dataclasses import dataclass

from aidm.models.state import Creature, GameState
from aidm.rules.scene import node_display_name


def display_name(index: str) -> str:
    return index.replace("-", " ").replace("_", " ").strip().title()


@dataclass(frozen=True)
class EntityRegistry:
    party: frozenset[str]
    npcs: frozenset[str]
    monsters: frozenset[str]
    dead: frozenset[str]
    features: frozenset[str]
    hidden_features: frozenset[str]
    items: frozenset[str]
    places: frozenset[str]
    lore: frozenset[str]

    @property
    def visible_names(self) -> frozenset[str]:
        return (
            self.party
            | self.npcs
            | self.monsters
            | self.features
            | self.items
            | self.places
            | self.lore
        )

    @property
    def all_names(self) -> frozenset[str]:
        return self.visible_names | self.dead | self.hidden_features

    def is_known(self, name: str) -> bool:
        wanted = name.strip().casefold()
        return any(n.casefold() == wanted for n in self.visible_names)


def _carried(creatures: list[Creature]) -> set[str]:
    names: set[str] = set()
    for creature in creatures:
        if creature.pc is None:
            continue
        names.update(display_name(i.item) for i in creature.pc.inventory)
    return names


def _places(state: GameState) -> set[str]:
    world = state.world
    nodes = set(world.neighbours) | set(world.node_names) | set(world.visited)
    for exits in world.neighbours.values():
        nodes.update(exits)
    return {node_display_name(state, n) for n in nodes}


def entity_registry(state: GameState) -> EntityRegistry:
    world = state.world
    creatures = list(state.creatures.values())
    shown = [f for f in world.features.values() if not f.hidden or f.discovered]
    hidden = [f for f in world.features.values() if f.hidden and not f.discovered]
    npc_names = {n.name for n in world.npcs.values()}
    return EntityRegistry(
        party=frozenset(c.name for c in creatures if c.pc is not None),
        npcs=frozenset(npc_names),
        monsters=frozenset(
            c.name for c in creatures if c.pc is None and not c.dead and c.name not in npc_names
        ),
        dead=frozenset(c.name for c in creatures if c.dead),
        features=frozenset(f.name for f in shown),
        hidden_features=frozenset(f.name for f in hidden),
        items=frozenset({i.name for i in world.items.values()} | _carried(creatures)),
        places=frozenset(_places(state)),
        lore=frozenset(world.lore_names),
    )
