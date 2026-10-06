"""Public projections of `GameState` for clients (SPEC 9, 10, 12): the ONLY place that turns
state into protocol views.

Privacy rules: NPCs go out only as `rules.social.public_npc_view` (no motive, no unrevealed
secret, no raw score); hidden features and hidden items are left out (via
`rules.scene.current_scene`); fact lines carrying private text are dropped; events go out only
through THE public projection in `session.public_feed`, never as raw events (NpcIntroduced and
CampaignInstalled embed motives and secrets).

Public API: `public_creature`, `public_scene`, `public_map`, `public_quests`, `public_combat`,
`public_offer`, `public_facts`, `public_summaries`, `public_state`, `stock_lines`
(dice views live in `session.public_feed`).
"""

from collections.abc import Sequence

from aidm.data.item_catalogue import CatalogueItem
from aidm.data.registry import Registry
from aidm.data.zone_templates import zone_templates
from aidm.dm.precheck import is_shop
from aidm.models.encounter import EncounterStatus
from aidm.models.protocol_views import (
    CombatToken,
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
    PublicSummary,
    PublicZone,
    QueueEntry,
    StockLine,
    TablePhase,
    VoteView,
)
from aidm.models.state import Creature, GameState
from aidm.models.world import QuestState
from aidm.models.zones import Zone
from aidm.rules.scene import current_scene, node_display_name
from aidm.rules.shop import StockEntry
from aidm.rules.social import public_npc_view
from aidm.session.public_feed import leaks, private_texts

MAX_PUBLIC_FACTS = 12
MAX_PUBLIC_SUMMARIES = 8


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
        stable=creature.stable and creature.hp == 0 and not creature.dead,
        death_save_successes=creature.death_save_successes,
        death_save_failures=creature.death_save_failures,
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
        shopkeepers=tuple(
            n.id
            for n in (world.npcs[i] for i in scene.npc_ids)
            if is_shop(state, n) and not n.hostile
        ),
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
    """Quest lines. Giver and objective are shown once the quest was taken on; an offered quest
    shows its giver only while the giver is in the party's place. Text naming private things is
    left out."""
    private = private_texts(state)
    plan = {q.id: q.objective for q in state.campaign.plan.quests} if state.campaign else {}
    out: list[PublicQuest] = []
    for q in sorted(state.world.quests.values(), key=lambda q: q.id):
        npc = state.world.npcs.get(q.giver_npc_id or "")
        taken = q.state is not QuestState.OFFERED
        here = npc is not None and npc.node_id == state.world.current_node
        giver = npc.name if npc is not None and (taken or here) else ""
        goal = plan.get(q.id, "") if taken else ""
        out.append(
            PublicQuest(
                id=q.id,
                title=q.title,
                state=q.state.value,
                giver=giver,
                objective="" if leaks(goal, private) else goal,
            )
        )
    return tuple(out)


def public_facts(state: GameState) -> tuple[str, ...]:
    """The latest ledger facts, minus any that carry private text (motive, secret, hidden)."""
    private = private_texts(state)
    facts = [f.text for f in state.world.facts if not leaks(f.text, private)]
    return tuple(facts[-MAX_PUBLIC_FACTS:])


def public_summaries(state: GameState) -> tuple[PublicSummary, ...]:
    """The latest scene summaries (guarded when written), minus any carrying private text."""
    private = private_texts(state)
    kept = [s for s in state.memory.summaries if not leaks(s.text + " " + s.title, private)]
    return tuple(PublicSummary(title=s.title, text=s.text) for s in kept[-MAX_PUBLIC_SUMMARIES:])


def _terrain_of(zone_id: str) -> str:
    return next(
        (t.index for t in zone_templates().all() if any(z.key == zone_id for z in t.zones)), ""
    )


def _public_zone(zone: Zone) -> PublicZone:
    return PublicZone(
        id=zone.id,
        name=zone.name,
        terrain=_terrain_of(zone.id),
        tags=tuple(zone.tags),
        distance_label=zone.distance_label,
        cover=zone.cover,
        high_ground=zone.high_ground,
        difficult=zone.difficult,
        surfaces=tuple(zone.surfaces),
    )


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
                monster_index=creature.monster_index,
            )
        )
    active = enc.active_id()
    return PublicCombat(
        encounter_id=enc.id,
        round=enc.round,
        zones=tuple(_public_zone(z) for z in enc.zone_map.zones),
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
    tts_enabled: bool = False,
    screens: int = 0,
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
        facts=public_facts(state),
        summaries=public_summaries(state),
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
        tts_enabled=tts_enabled,
        screens=screens,
        monster_hp=state.difficulty.monster_hp,
        monster_damage=state.difficulty.monster_damage,
    )


def stock_lines(
    entries: Sequence[StockEntry], catalogue: Registry[CatalogueItem]
) -> tuple[StockLine, ...]:
    lines: list[StockLine] = []
    for entry in entries:
        item = catalogue.find(entry.item)
        name = item.name if item is not None else entry.item.replace("-", " ")
        lines.append(
            StockLine(
                item_id=entry.item,
                name=name,
                price_gp=entry.price_gp,
                category=item.category.value if item is not None else "",
                supply=item.supply if item is not None else 0,
            )
        )
    return tuple(lines)
