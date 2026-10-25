"""What the out-of-fight menu builders share: the hero's view of the place (M36.3, SPEC 6.2). Pure.

`SceneMenuView` gathers once what every scene, item and offer entry builder reads: the state,
the hero's sheet (the item cards' own source, `rules.sheet.build_sheet` with the hero's lit
light), the people standing here (`rules.scene.current_scene`, the dead never), the other
heroes (downed ones included, the fallen never), the encounter offer pending at this place and
whether its foes are still a threat (`rules.waiting_foe`).

Targets, each labelled for a model choosing:
- people: "Widow Cabrelle (silent keeper of the inn)", ", hostile" when so;
- heroes: "Tamsin, down", the hero "Brienne (you), unhurt"; M36.4: a dead hero ("Tamsin,
  dead") only as the source of a `loot:` entry (`fallen_heroes`);
- places: every place the party knows (visited, or the next road from one) with the walk from
  here over the roads open now (`rules.world_graph.travel_route`): "next door", "2 roads away",
  "you are here", a locked way's short reason (`rules.gateway_lock.short_reason`), or "no open
  road from here";
- things: the discovered features of this place ("Iron Door, locked");
- offer foes: `foe:<monster>` per kind ("Kobold x3") and the master by NPC id.

Public API: `SceneMenuView`, `scene_view(state, actor_id, regs)`, `Place`, `places(view)`,
`scene_targets(view)`, `offer_foes(view)`, `fallen_heroes(view)`, `HERE_NOTE`, `NO_ROAD_NOTE`,
`FOE_PREFIX`.
"""

from dataclasses import dataclass

from aidm.data.combat_data import CombatRegistries
from aidm.models.action_menu import MenuTarget
from aidm.models.campaign_state import EncounterOffer
from aidm.models.sheet import CharacterSheet
from aidm.models.state import GameState
from aidm.rules.gateway_lock import locked_reason, short_reason
from aidm.rules.light import hero_light
from aidm.rules.menu_labels import state_word
from aidm.rules.scene import current_scene, node_display_name
from aidm.rules.sheet import build_sheet
from aidm.rules.waiting_foe import waiting_foe
from aidm.rules.world_graph import travel_route

HERE_NOTE = "you are here"
NO_ROAD_NOTE = "no open road from here"
FOE_PREFIX = "foe:"


@dataclass(frozen=True)
class SceneMenuView:
    state: GameState
    actor_id: str
    regs: CombatRegistries
    sheet: CharacterSheet
    people: tuple[str, ...]
    heroes: tuple[str, ...]
    offer: EncounterOffer | None
    threat: bool

    @property
    def gold(self) -> int:
        return self.sheet.gold


def scene_view(state: GameState, actor_id: str, regs: CombatRegistries) -> SceneMenuView:
    creature = state.creatures[actor_id]
    light = hero_light(state, actor_id)
    sheet = build_sheet(creature, regs.chars, None, light.item if light is not None else None)
    heroes = sorted(
        c.id
        for c in state.creatures.values()
        if c.pc is not None and not c.dead and c.id != actor_id
    )
    campaign = state.campaign
    offer = campaign.offer if campaign is not None else None
    here = offer if offer is not None and offer.node_id == state.world.current_node else None
    return SceneMenuView(
        state=state,
        actor_id=actor_id,
        regs=regs,
        sheet=sheet,
        people=current_scene(state).npc_ids,
        heroes=tuple(heroes),
        offer=here,
        threat=waiting_foe(state) is not None,
    )


@dataclass(frozen=True)
class Place:
    node_id: str
    label: str
    note: str
    hops: int
    locked: bool


def _known(state: GameState) -> list[str]:
    world = state.world
    seen = [*world.visited, *(world.current_node or "",)]
    known = dict.fromkeys(n for n in seen if n)
    for node in seen:
        known.update(dict.fromkeys(world.neighbours.get(node, ())))
    return list(known)


def _place(state: GameState, node: str) -> Place:
    world = state.world
    name = node_display_name(state, node)
    if node == world.current_node:
        return Place(node, f"{name}, {HERE_NOTE}", HERE_NOTE, 0, False)
    route = travel_route(world, world.current_node or "", node) if world.current_node else None
    if route:
        hops = len(route)
        walk = "next door" if hops == 1 else f"{hops} roads away"
        return Place(node, f"{name}, {walk}", "", hops, False)
    reason = locked_reason(state, node)
    if reason is not None and node in world.neighbours.get(world.current_node or "", ()):
        return Place(node, f"{name}, {short_reason(state, node)}", reason, -1, True)
    return Place(node, f"{name}, {NO_ROAD_NOTE}", NO_ROAD_NOTE, -1, False)


def places(view: SceneMenuView) -> list[Place]:
    """Every known place: the open ones by distance, then here, then the shut ones."""
    found = [_place(view.state, node) for node in _known(view.state)]

    def order(place: Place) -> tuple[int, int]:
        if place.hops > 0:
            return 0, place.hops
        return (1, 0) if place.hops == 0 else (2, 0 if place.locked else 1)

    return sorted(found, key=order)


def _person_label(view: SceneMenuView, npc_id: str) -> str:
    npc = view.state.world.npcs[npc_id]
    label = f"{npc.name} ({npc.role})" if npc.role else npc.name
    return f"{label}, hostile" if npc.hostile else label


def _hero_label(view: SceneMenuView, creature_id: str) -> str:
    creature = view.state.creatures[creature_id]
    you = " (you)" if creature_id == view.actor_id else ""
    return f"{creature.name}{you}, {state_word(creature)}"


def offer_foes(view: SceneMenuView) -> list[MenuTarget]:
    offer = view.offer
    if offer is None:
        return []
    out: list[MenuTarget] = []
    boss = view.state.world.npcs.get(offer.boss_npc_id or "")
    if boss is not None:
        out.append(MenuTarget(id=boss.id, label=f"{boss.name} (master)", kind="foe"))
    counts = dict.fromkeys(offer.monster_ids, 0)
    for monster in offer.monster_ids:
        counts[monster] += 1
    for monster, count in counts.items():
        found = view.regs.monsters.find(monster)
        name = found.name if found is not None else monster.replace("-", " ").title()
        label = f"{name} x{count}" if count > 1 else name
        out.append(MenuTarget(id=f"{FOE_PREFIX}{monster}", label=label, kind="foe"))
    return out


def _features(view: SceneMenuView) -> list[MenuTarget]:
    world = view.state.world
    out: list[MenuTarget] = []
    for feature_id in current_scene(view.state).feature_ids:
        feature = world.features[feature_id]
        label = f"{feature.name}, locked" if feature.lock is not None else feature.name
        out.append(MenuTarget(id=feature.id, label=label, kind="thing"))
    return out


def fallen_heroes(view: SceneMenuView) -> tuple[str, ...]:
    """M36.4 Y14: the other heroes who are down or dead (their packs can be taken from)."""
    return tuple(
        sorted(
            c.id
            for c in view.state.creatures.values()
            if c.pc is not None and c.id != view.actor_id and (c.dead or c.hp <= 0)
        )
    )


def scene_targets(view: SceneMenuView) -> list[MenuTarget]:
    """Every target an out-of-fight entry may name (the menu keeps the ones named)."""
    out = [MenuTarget(id=n, label=_person_label(view, n), kind="person") for n in view.people]
    out.append(MenuTarget(id=view.actor_id, label=_hero_label(view, view.actor_id), kind="self"))
    heroes = (*view.heroes, *(h for h in fallen_heroes(view) if h not in view.heroes))
    out += [MenuTarget(id=h, label=_hero_label(view, h), kind="ally") for h in heroes]
    out += offer_foes(view)
    out += _features(view)
    out += [MenuTarget(id=p.node_id, label=p.label, kind="place") for p in places(view)]
    unique = {t.id: t for t in reversed(out)}  # the first of a clash wins (a master standing here)
    return [unique[t.id] for t in out if unique[t.id] is t]
