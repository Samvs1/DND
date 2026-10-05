"""World-pulled encounters: the offer on arrival and the fight it may become (SPEC 9). Pure.

Encounters are pulled by the world, never by a timer. Policy (deterministic for the campaign
seed and the node state):
- a spoke with encounter themes offers its encounter once, on the first arrival;
- the gateway offers the boss on every arrival while the region is unresolved and the boss is
  neither defeated nor allied;
- the arrival node is always safe.
Monsters come from the node's themes within the CR budget of the party (medium for a spoke,
hard for the boss's company; `aidm.rules.encounter_budget`); a theme list too costly for the
party still yields its cheapest monster (the warning beat lets the party escape or parley).
Nothing starts without the warning beat: the offer lists fight / surprise / escape / parley
(answered by `aidm.rules.offer_answer`).

Public API:
- `OfferData(monsters, tables, terrains, tiers)`: the registries (passed in).
- `arrival_offer_events(state, data, retreat_node) -> list[AnyEvent]`: `[EncounterOffered]` or [].
- `offer_fight_events(state, offer, data, rng, surprise) -> list[AnyEvent]`: the boss turns
  hostile if needed, then `rules.encounter.start_encounter` on a zone map from the node terrain.
"""

import random
from dataclasses import dataclass

from aidm.data.dm_tiers import DmTiers
from aidm.data.encounter_tables import EncounterTables
from aidm.data.registry import Registry
from aidm.data.srd_monsters import SrdMonster
from aidm.data.zone_templates import TerrainTemplate
from aidm.models.campaign import NodePlan, RegionPlan
from aidm.models.campaign_events import EncounterOffered
from aidm.models.campaign_state import EncounterOffer
from aidm.models.checks import DcTier
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.encounter import (
    Difficulty,
    EncounterSetup,
    EncounterStatus,
    MonsterSpawn,
    PartyPlacement,
    SurpriseKind,
)
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.rules.checks import dc_for_tier
from aidm.rules.dice import Rng
from aidm.rules.dm_tiers import party_levels
from aidm.rules.encounter import start_encounter
from aidm.rules.encounter_budget import adjusted_xp, party_budget, pick_monsters, rate_encounter
from aidm.rules.progression import boss_defeated, boss_npc, node_plan, region_of
from aidm.rules.social import attitude_band, attitude_score, hostile_attitude_events
from aidm.rules.zone_gen import generate_zone_map
from aidm.rules.zones import zone_neighbors


@dataclass(frozen=True)
class OfferData:
    monsters: Registry[SrdMonster]
    tables: EncounterTables
    terrains: Registry[TerrainTemplate]
    tiers: DmTiers


def _boss_waits(state: GameState, region: RegionPlan) -> WorldNpc | None:
    campaign = state.campaign
    npc = boss_npc(state, region)
    if campaign is None or npc is None or region.id in campaign.resolved:
        return None
    if boss_defeated(state, region):
        return None
    if not npc.hostile and attitude_band(attitude_score(npc)) is AttitudeBand.ALLY:
        return None
    return npc


def _xp(data: OfferData, monster: str) -> int:
    return data.monsters.get(monster).xp


def _company(
    rng: Rng, data: OfferData, themes: tuple[str, ...], budget: int, lead: list[str], size: int
) -> list[str]:
    """`lead` plus theme monsters added at random while the adjusted XP stays within budget."""
    picked = list(lead)
    pool = sorted(set(themes))
    while len(picked) < data.tables.max_monsters and pool:
        xps = [_xp(data, m) for m in picked]
        fits = [m for m in pool if adjusted_xp([*xps, _xp(data, m)], size, data.tables) <= budget]
        if not fits:
            break
        picked.append(fits[rng.randint(0, len(fits) - 1)])
    return picked


def _monsters(
    state: GameState, data: OfferData, node: NodePlan, boss: WorldNpc | None, rng: Rng
) -> list[str]:
    levels = party_levels(state)
    size = len(levels)
    if boss is not None:
        hard = party_budget(levels, Difficulty.HARD, data.tables)
        return _company(rng, data, node.encounter_themes, hard, [boss.archetype_id], size)[1:]
    medium = party_budget(levels, Difficulty.MEDIUM, data.tables)
    xps = {m: _xp(data, m) for m in node.encounter_themes}
    picked = pick_monsters(rng, medium, xps, size, data.tables)
    return picked or [min(sorted(xps), key=lambda m: xps[m])]


def _dc(table: dict[str, str], tier: int) -> int:
    return dc_for_tier(DcTier(table.get(str(tier), DcTier.MEDIUM.value)))


def _offer(
    state: GameState,
    data: OfferData,
    where: tuple[RegionPlan, NodePlan],
    boss: WorldNpc | None,
    retreat_node: str | None,
) -> EncounterOffer:
    region, node = where
    campaign = state.campaign
    seed = campaign.seed if campaign is not None else state.seed
    rng = random.Random(f"{seed}:{node.id}:{state.world.scene_index}")
    monsters = _monsters(state, data, node, boss, rng)
    xps = [_xp(data, m) for m in monsters]
    if boss is not None:
        xps.append(_xp(data, boss.archetype_id))
    rated = rate_encounter(xps, party_levels(state), data.tables)
    common = _dc(data.tiers.offer_dc_tiers, region.tier)
    parley = _dc(data.tiers.boss_parley_dc_tiers, region.tier) if boss else common
    return EncounterOffer(
        id=f"offer-{state.event_count}",
        node_id=node.id,
        region_id=region.id,
        monster_ids=tuple(monsters),
        boss_npc_id=boss.id if boss is not None else None,
        difficulty=rated.value if rated is not None else "trivial",
        retreat_node=retreat_node,
        escape_dc=common,
        parley_dc=parley,
        surprise_dc=common,
    )


def arrival_offer_events(
    state: GameState, data: OfferData, retreat_node: str | None
) -> list[AnyEvent]:
    campaign = state.campaign
    node_id = state.world.current_node
    region, node = region_of(state, node_id), node_plan(state, node_id)
    if campaign is None or region is None or node is None or campaign.offer is not None:
        return []
    if state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE:
        return []
    if not party_levels(state):
        return []
    boss = _boss_waits(state, region) if node.id == region.gateway.id else None
    if boss is None and (not node.encounter_themes or node.id in campaign.offered_nodes):
        return []
    if boss is None and node.id == region.gateway.id:
        return []
    return [EncounterOffered(offer=_offer(state, data, (region, node), boss, retreat_node))]


def _setup(
    state: GameState, offer: EncounterOffer, data: OfferData, rng: Rng, surprise: SurpriseKind
) -> EncounterSetup:
    node = node_plan(state, offer.node_id)
    tags = node.terrain_tags if node is not None else ()
    zone_map = generate_zone_map(rng, tags, data.terrains)
    start = zone_map.zones[0].id
    foes = zone_neighbors(zone_map, start)[0][0]
    spawns = [MonsterSpawn(monster=m, zone_id=foes) for m in offer.monster_ids]
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if boss is not None:
        spawns.insert(0, MonsterSpawn(monster=boss.archetype_id, zone_id=foes, name=boss.name))
    pcs = sorted(c.id for c in state.creatures.values() if c.pc is not None and not c.dead)
    return EncounterSetup(
        encounter_id=f"enc-{state.event_count}",
        zone_map=zone_map,
        party=tuple(PartyPlacement(creature_id=pc, zone_id=start) for pc in pcs),
        monsters=tuple(spawns),
        surprise=surprise,
    )


def offer_fight_events(
    state: GameState, offer: EncounterOffer, data: OfferData, rng: Rng, surprise: SurpriseKind
) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if boss is not None and not boss.hostile:
        events.extend(hostile_attitude_events(boss, "the party fights them"))
    setup = _setup(state, offer, data, rng, surprise)
    events.extend(start_encounter(rng, state, setup, data.monsters))
    return events
