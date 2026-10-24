"""The current scene as a derived, read-only view of state (SPEC 2.2 closed world, 6.4, 9).

Nothing here is stored twice: presence comes from `WorldNpc.node_id` (a dead NPC is never
present, M20.5), visibility from
`WorldFeature.hidden/discovered` and `WorldItem.hidden`, exits from `World.neighbours`. The
context builder (`aidm.dm.context`) renders this view as the scene manifest, so anything not in
it does not exist for the narrator.

Public API:
- `SceneView(node_id, node_name, description, party_ids, npc_ids, monster_ids, fallen_ids,
  feature_ids, item_ids, exits, locked_exits, turn)`: ids in deterministic (sorted) order.
- `current_scene(state) -> SceneView`.
- `node_display_name(state, node_id) -> str`: `World.node_names` or the humanised id.
- `is_search_check(what) -> bool` (M27.2): Perception, Investigation or a WIS/INT ability check
  (the search checks; darkness puts them at disadvantage, `aidm.rules.light`).
- `discovery_events(state, creature_id, result) -> list[FeatureDiscovered | ItemDiscovered]`: a
  Perception or Investigation check (or a WIS/INT ability check) finds every hidden, undiscovered
  feature in the current place whose `discover_dc` is at most the roll total
  (`FeatureDiscovered`), then every hidden item there whose `discover_dc` it meets
  (`ItemDiscovered`, M23.3: hidden quest items).
- `hidden_dc(state) -> int | None` (M31.1a V9): the lowest discover DC of what is hidden here, the
  ONE DC a search check rolls against when something is hidden (the storyteller's and the
  typed search's alike), so the verdict and the find always agree.
"""

from dataclasses import dataclass

from aidm.models.abilities import Ability, Skill
from aidm.models.checks import CheckKind, CheckResult
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.state import GameState
from aidm.models.world_events import FeatureDiscovered, ItemDiscovered

_SEARCH_SKILLS = (Skill.PERCEPTION, Skill.INVESTIGATION)
_SEARCH_ABILITIES = (Ability.WIS, Ability.INT)


@dataclass(frozen=True)
class SceneView:
    node_id: str | None
    node_name: str
    description: str
    party_ids: tuple[str, ...]
    npc_ids: tuple[str, ...]
    monster_ids: tuple[str, ...]
    fallen_ids: tuple[str, ...]
    feature_ids: tuple[str, ...]
    item_ids: tuple[str, ...]
    exits: tuple[str, ...]
    locked_exits: tuple[str, ...]
    turn: int


def node_display_name(state: GameState, node_id: str | None) -> str:
    if node_id is None:
        return "here"
    name = state.world.node_names.get(node_id)
    return name if name else node_id.replace("-", " ").replace("_", " ").title()


def _foes(state: GameState) -> tuple[tuple[str, ...], tuple[str, ...]]:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return (), ()
    living: list[str] = []
    fallen: list[str] = []
    for cid, combatant in sorted(enc.combatants.items()):
        creature = state.creatures.get(cid)
        if creature is None or combatant.side is Side.PARTY or creature.pc is not None:
            continue
        if creature.dead:
            fallen.append(cid)
        elif combatant.withdrawn is None:
            living.append(cid)
    return tuple(living), tuple(fallen)


def current_scene(state: GameState) -> SceneView:
    world = state.world
    node = world.current_node
    party = sorted(c.id for c in state.creatures.values() if c.pc is not None and not c.dead)
    npcs = sorted(n.id for n in world.npcs.values() if n.node_id == node and not n.dead)
    features = sorted(
        f.id
        for f in world.features.values()
        if f.node_id == node and (not f.hidden or f.discovered)
    )
    items = sorted(i.id for i in world.items.values() if i.node_id == node and not i.hidden)
    exits = tuple(world.neighbours.get(node, ())) if node is not None else ()
    locked = tuple(e for e in exits if e in world.locked_nodes)
    living, fallen = _foes(state)
    return SceneView(
        node_id=node,
        node_name=node_display_name(state, node),
        description=world.descriptions.get(node, "") if node is not None else "",
        party_ids=tuple(party),
        npc_ids=tuple(npcs),
        monster_ids=living,
        fallen_ids=fallen,
        feature_ids=tuple(features),
        item_ids=tuple(items),
        exits=exits,
        locked_exits=locked,
        turn=world.scene_turn,
    )


def is_search_check(what: Skill | Ability) -> bool:
    return what in _SEARCH_SKILLS if isinstance(what, Skill) else what in _SEARCH_ABILITIES


def _is_search(result: CheckResult) -> bool:
    if result.kind is CheckKind.SKILL:
        return result.skill is not None and is_search_check(result.skill)
    return result.kind is CheckKind.ABILITY and result.ability in _SEARCH_ABILITIES


def hidden_dc(state: GameState) -> int | None:
    """The lowest discover DC of the hidden, undiscovered features and the hidden items of the
    current place (M31.1a V9: one search check, one DC); None when nothing is hidden here."""
    node = state.world.current_node
    dcs = [
        f.discover_dc
        for f in state.world.features.values()
        if f.node_id == node and f.hidden and not f.discovered and f.discover_dc is not None
    ]
    dcs += [
        i.discover_dc
        for i in state.world.items.values()
        if i.node_id == node and i.hidden and i.discover_dc is not None
    ]
    return min(dcs, default=None)


def discovery_events(
    state: GameState, creature_id: str, result: CheckResult
) -> list[FeatureDiscovered | ItemDiscovered]:
    if not _is_search(result):
        return []
    node = state.world.current_node
    total = result.roll.total
    found = sorted(
        f.id
        for f in state.world.features.values()
        if f.node_id == node
        and f.hidden
        and not f.discovered
        and f.discover_dc is not None
        and total >= f.discover_dc
    )
    items = sorted(
        i.id
        for i in state.world.items.values()
        if i.node_id == node and i.hidden and i.discover_dc is not None and total >= i.discover_dc
    )
    events: list[FeatureDiscovered | ItemDiscovered] = [
        FeatureDiscovered(feature_id=fid, creature_id=creature_id) for fid in found
    ]
    return events + [ItemDiscovered(item_id=iid, creature_id=creature_id) for iid in items]
