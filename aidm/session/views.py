"""Public projections of `GameState` for clients (SPEC 9, 10, 12): the ONLY place that turns
state into protocol views.

Privacy rules: NPCs go out only as `rules.social.public_npc_view` (no motive, no unrevealed
secret, no raw score); hidden features and hidden items are left out (via
`rules.scene.current_scene`); events go out as `{seq, kind, line}` with the public log line of
`dm.event_text.event_line`, never the raw event (NpcIntroduced and CampaignInstalled embed
motives and secrets).

Public API: `public_creature`, `public_scene`, `public_map`, `public_quests`, `public_combat`,
`public_offer`, `public_state`, `event_message`, `dice_view`, `stock_lines`.
"""

from collections.abc import Sequence

from aidm.data.item_catalogue import CatalogueItem
from aidm.data.registry import Registry
from aidm.dm.event_text import event_line
from aidm.models.combat_events import AttackRolled
from aidm.models.dice import AdvState, D20Roll
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, CheckResolved, DeathSaveRolled, DiceRolled
from aidm.models.protocol_server import EventMsg
from aidm.models.protocol_views import (
    CombatToken,
    DiceView,
    MapNode,
    PlayerInfo,
    PublicCombat,
    PublicCreature,
    PublicExit,
    PublicFeature,
    PublicMap,
    PublicOffer,
    PublicQuest,
    PublicScene,
    PublicState,
    QueueEntry,
    StockLine,
    TablePhase,
    VoteView,
)
from aidm.models.state import Creature, GameState
from aidm.rules.scene import current_scene, node_display_name
from aidm.rules.shop import StockEntry
from aidm.rules.social import public_npc_view

MAX_PUBLIC_FACTS = 12


def public_creature(creature: Creature) -> PublicCreature:
    pc = creature.pc
    return PublicCreature(
        id=creature.id,
        name=creature.name,
        kind=creature.kind.value,
        hp=creature.hp,
        max_hp=creature.max_hp,
        temp_hp=creature.temp_hp,
        ac=creature.ac,
        conditions=tuple(c.name for c in creature.conditions),
        dead=creature.dead,
        dying=creature.hp == 0 and not creature.dead and not creature.stable,
        level=pc.level if pc is not None else None,
        race=pc.race if pc is not None else None,
        class_index=pc.class_index if pc is not None else None,
        portrait_id=pc.portrait_id if pc is not None else "",
        gold=pc.gold if pc is not None else None,
        xp=pc.xp if pc is not None else None,
    )


def public_scene(state: GameState) -> PublicScene | None:
    scene = current_scene(state)
    if scene.node_id is None:
        return None
    world = state.world
    exits = tuple(
        PublicExit(
            node_id=node,
            name=node_display_name(state, node),
            locked=node in scene.locked_exits,
            visited=node in world.visited,
        )
        for node in scene.exits
    )
    features = tuple(
        PublicFeature(id=f.id, kind=f.kind.value, name=f.name, description=f.description)
        for f in (world.features[fid] for fid in scene.feature_ids)
    )
    return PublicScene(
        node_id=scene.node_id,
        name=scene.node_name,
        description=scene.description,
        exits=exits,
        npcs=tuple(public_npc_view(world.npcs[nid]) for nid in scene.npc_ids),
        features=features,
        items=tuple(world.items[iid].name for iid in scene.item_ids),
        shop_npc_id=world.shop_npc_id,
    )


def public_map(state: GameState) -> PublicMap | None:
    world = state.world
    if world.current_node is None:
        return None
    seen = set(world.visited) | {world.current_node}
    shown = set(seen)
    for node in seen:
        shown.update(world.neighbours.get(node, ()))
    nodes = tuple(
        MapNode(
            id=node,
            name=node_display_name(state, node) if node in seen else "Unexplored",
            visited=node in world.visited,
            locked=node in world.locked_nodes,
            current=node == world.current_node,
        )
        for node in sorted(shown)
    )
    edges = sorted(
        {tuple(sorted((a, b))) for a in seen for b in world.neighbours.get(a, ()) if b in shown}
    )
    return PublicMap(nodes=nodes, edges=tuple((a, b) for a, b in edges))


def public_quests(state: GameState) -> tuple[PublicQuest, ...]:
    quests = sorted(state.world.quests.values(), key=lambda q: q.id)
    return tuple(PublicQuest(id=q.id, title=q.title, state=q.state.value) for q in quests)


def public_combat(state: GameState) -> PublicCombat | None:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return None
    tokens: list[CombatToken] = []
    for cid, combatant in sorted(enc.combatants.items()):
        creature = state.creatures[cid]
        tokens.append(
            CombatToken(
                creature_id=cid,
                name=creature.name,
                side=combatant.side,
                zone_id=combatant.zone_id,
                hp=creature.hp,
                max_hp=creature.max_hp,
                conditions=tuple(c.name for c in creature.conditions),
                dead=creature.dead,
                withdrawn=combatant.withdrawn is not None,
            )
        )
    active = enc.active_id()
    return PublicCombat(
        encounter_id=enc.id,
        round=enc.round,
        zones=tuple(enc.zone_map.zones),
        edges=tuple(enc.zone_map.edges),
        tokens=tuple(tokens),
        initiative=tuple(e.creature_id for e in enc.initiative),
        active_id=active,
        economy=enc.combatant(active).economy if active is not None else None,
    )


def public_offer(state: GameState) -> PublicOffer | None:
    offer = state.campaign.offer if state.campaign is not None else None
    if offer is None:
        return None
    foes = [state.creatures[m].name for m in offer.monster_ids if m in state.creatures]
    if not foes:
        foes = [m.replace("-", " ") for m in offer.monster_ids]
    boss = state.world.npcs.get(offer.boss_npc_id) if offer.boss_npc_id else None
    return PublicOffer(
        id=offer.id,
        node_id=offer.node_id,
        foes=tuple(foes),
        boss_name=boss.name if boss is not None else None,
        difficulty=offer.difficulty,
        options=offer.options,
    )


def public_state(
    state: GameState,
    *,
    phase: TablePhase,
    paused: bool,
    players: Sequence[PlayerInfo],
    queue: Sequence[QueueEntry] = (),
    resolving: QueueEntry | None = None,
    vote: VoteView | None = None,
) -> PublicState:
    campaign = state.campaign
    party = sorted((c for c in state.creatures.values() if c.pc is not None), key=lambda c: c.id)
    return PublicState(
        campaign_id=state.campaign_id,
        phase=phase,
        paused=paused,
        players=tuple(players),
        party=tuple(public_creature(c) for c in party),
        scene=public_scene(state),
        map=public_map(state),
        quests=public_quests(state),
        facts=tuple(f.text for f in state.world.facts[-MAX_PUBLIC_FACTS:]),
        combat=public_combat(state),
        offer=public_offer(state),
        queue=tuple(queue),
        resolving=resolving,
        vote=vote,
        campaign_title=campaign.plan.title if campaign is not None else "",
        region_tier=state.world.region_tier,
        camp_supplies=state.camp_supplies,
        complete=campaign.complete if campaign is not None else False,
        epilogue=campaign.epilogue if campaign is not None else None,
    )


def event_message(state: GameState, seq: int, event: AnyEvent) -> EventMsg:
    return EventMsg(seq=seq, kind=event.type, line=event_line(state, event) or "")


def _d20(roller: str | None, label: str, roll: D20Roll, target: int | None) -> DiceView:
    return DiceView(
        roller_id=roller,
        label=label,
        expression="1d20" if roll.adv is AdvState.NORMAL else "2d20",
        rolls=roll.rolls,
        adv=roll.adv,
        modifier=roll.modifier,
        total=roll.total,
        target=target,
        crit=roll.is_crit,
    )


def dice_view(event: AnyEvent) -> DiceView | None:
    if isinstance(event, AttackRolled):
        view = _d20(event.attacker_id, event.attack, event.roll, event.target_ac)
        return view.model_copy(update={"success": event.hit, "crit": event.crit})
    if isinstance(event, CheckResolved):
        r = event.result
        label = r.skill.value if r.skill is not None else f"{r.ability.value} {r.kind.value}"
        view = _d20(event.creature_id, label, r.roll, r.dc)
        return view.model_copy(update={"success": r.success})
    if isinstance(event, DeathSaveRolled):
        view = _d20(event.creature_id, "death save", event.roll, 10)
        return view.model_copy(update={"success": event.roll.total >= 10})
    if isinstance(event, DiceRolled):
        r = event.roll
        return DiceView(
            roller_id=event.roller_id,
            label=event.label,
            expression=r.expression,
            rolls=tuple(d.value for d in r.dice if d.kept),
            modifier=r.modifier,
            total=r.total,
        )
    return None


def stock_lines(
    entries: Sequence[StockEntry], catalogue: Registry[CatalogueItem]
) -> tuple[StockLine, ...]:
    lines: list[StockLine] = []
    for entry in entries:
        item = catalogue.find(entry.item)
        name = item.name if item is not None else entry.item.replace("-", " ")
        lines.append(StockLine(item_id=entry.item, name=name, price_gp=entry.price_gp))
    return tuple(lines)
