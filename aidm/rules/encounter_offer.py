"""World-pulled encounters: the offer on arrival and the fight it may become (SPEC 9). Pure.

Encounters are pulled by the world, never by a timer. Policy (deterministic for the campaign
seed and the node state):
- a spoke with encounter themes offers its encounter once, on the first arrival;
- the gateway offers the boss on every arrival while the region is unresolved and the boss is
  neither defeated nor allied;
- the arrival node is always safe.
Monsters come from the node's themes within the CR budget of the actual party (size and
levels): a spoke's list is rated at most `tables.spoke_rating_cap[region tier]` (tier 1: easy)
and fields at most `spoke_max_monsters_per_pc` monsters per PC; the boss and its company are
rated at most `tables.boss_rating_cap` (hard) (`aidm.rules.encounter_budget.rating_cap_xp`,
RULES_DECISIONS M9.2); a theme list too costly for the party gets terrain-matched stand-ins
within the budget when `tables.spoke_stand_ins` is on (M29.6), else (or when none fits) its
cheapest monster (the warning beat lets the party escape or parley). The boss's company is also
capped at `tables.boss_company_max_per_pc` per hero. A finished Cunning route of the region's
main quest (`rules.quest_progress.route_effects`, M23.2) changes the boss fight: `boss_alone`
offers the boss without company, `boss_surprised` starts the fight with the boss side surprised.
Nothing starts without the warning beat: the offer lists fight / surprise / escape / parley
(answered by `aidm.rules.offer_answer`).

Public API:
- `OfferData(monsters, tables, terrains, tiers, encounter)`: the registries (passed in).
- `arrival_offer_events(state, data, retreat_node) -> list[AnyEvent]`: `[EncounterOffered]` or [].
- `boss_hp_scale(state, data, monster) -> float`: the boss spawn's hit point scale (M29.6).
- `offer_fight_events(state, offer, data, rng, surprise) -> list[AnyEvent]`: the boss turns
  hostile if needed, then `rules.encounter.start_encounter` on a zone map from the node terrain.
"""

import random
from dataclasses import dataclass

from aidm.data.dm_tiers import DmTiers
from aidm.data.encounter_monsters import EncounterMonster
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
from aidm.rules.encounter_budget import adjusted_xp, pick_monsters, rate_encounter, rating_cap_xp
from aidm.rules.finale import finale_open
from aidm.rules.progression import boss_defeated, boss_npc, node_plan, region_of
from aidm.rules.quest_progress import route_effects
from aidm.rules.social import attitude_band, attitude_score, hostile_attitude_events
from aidm.rules.zone_gen import generate_zone_map
from aidm.rules.zones import zone_neighbors


@dataclass(frozen=True)
class OfferData:
    monsters: Registry[SrdMonster]
    tables: EncounterTables
    terrains: Registry[TerrainTemplate]
    tiers: DmTiers
    encounter: Registry[EncounterMonster]


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
    """`lead` plus theme monsters added at random while the adjusted XP stays within budget
    (and the company within `boss_company_max_per_pc` per hero, M29.6)."""
    picked = list(lead)
    pool = sorted(set(themes))
    limit = data.tables.max_monsters
    per_pc = data.tables.boss_company_max_per_pc
    if per_pc is not None:
        limit = min(limit, len(lead) + per_pc * size)
    while len(picked) < limit and pool:
        xps = [_xp(data, m) for m in picked]
        fits = [m for m in pool if adjusted_xp([*xps, _xp(data, m)], size, data.tables) <= budget]
        if not fits:
            break
        picked.append(fits[rng.randint(0, len(fits) - 1)])
    return picked


def _boss_themes(region: RegionPlan, node: NodePlan) -> tuple[str, ...]:
    """The boss's company: its lair's themes, else the region's (M20.6, playtest 3: a lair has no
    themes of its own, so the region boss, a lone acolyte, was a trivial fight)."""
    if node.encounter_themes:
        return node.encounter_themes
    return tuple(sorted({m for n in region.nodes() for m in n.encounter_themes}))


def _spoke_tables(data: OfferData, tier: int, size: int) -> EncounterTables:
    per_pc = data.tables.spoke_max_monsters_per_pc.get(tier)
    if per_pc is None:
        return data.tables
    return data.tables.model_copy(
        update={"max_monsters": min(data.tables.max_monsters, per_pc * size)}
    )


def _monsters(
    state: GameState,
    data: OfferData,
    where: tuple[RegionPlan, NodePlan],
    boss: WorldNpc | None,
    rng: Rng,
) -> list[str]:
    region, node = where
    levels = party_levels(state)
    size = len(levels)
    if boss is not None:
        cap = rating_cap_xp(levels, Difficulty(data.tables.boss_rating_cap), data.tables)
        if "boss_alone" in route_effects(state, region):
            return []
        themes = _boss_themes(region, node)
        return _company(rng, data, themes, cap, [boss.archetype_id], size)[1:]
    rating = data.tables.spoke_rating_cap.get(region.tier, Difficulty.MEDIUM.value)
    scale = data.tables.spoke_budget_scale.get(region.tier, 1.0)
    cap = int(rating_cap_xp(levels, Difficulty(rating), data.tables) * scale)
    xps = {m: _xp(data, m) for m in node.encounter_themes}
    tables = _spoke_tables(data, region.tier, size)
    picked = pick_monsters(rng, cap, xps, size, tables)
    if not picked and data.tables.spoke_stand_ins:
        picked = _stand_ins(rng, data, node.encounter_themes, (cap, size), tables)
    return picked or [min(sorted(xps), key=lambda m: xps[m])]


def _stand_ins(
    rng: Rng,
    data: OfferData,
    themes: tuple[str, ...],
    budget: tuple[int, int],
    tables: EncounterTables,
) -> list[str]:
    """M29.6: no theme monster fits the party's budget (a small or low-level party) -> the
    encounter-ready monsters sharing a terrain with the themes, at the highest XP one of them
    fits alone, picked within the budget. [] when none fits (the cheapest theme monster stays)."""
    cap, size = budget
    tags = {t for m in themes if (e := data.encounter.find(m)) is not None for t in e.tags}
    fits = {
        e.index: _xp(data, e.index)
        for e in data.encounter.all()
        if tags & set(e.tags) and adjusted_xp([_xp(data, e.index)], size, tables) <= cap
    }
    if not fits:
        return []
    top = max(fits.values())
    return pick_monsters(rng, cap, {m: x for m, x in fits.items() if x == top}, size, tables)


def boss_hp_scale(state: GameState, data: OfferData, monster: str) -> float:
    """M29.6: a boss whose own adjusted XP is over the boss cap for this party (a solo or duo)
    gets its hit points scaled by cap / adjusted XP, floored at `boss_hp_scale_floor`."""
    floor = data.tables.boss_hp_scale_floor
    levels = party_levels(state)
    if floor is None or not levels:
        return 1.0
    cap = rating_cap_xp(levels, Difficulty(data.tables.boss_rating_cap), data.tables)
    alone = adjusted_xp([_xp(data, monster)], len(levels), data.tables)
    return 1.0 if alone <= cap else max(floor, cap / alone)


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
    monsters = _monsters(state, data, where, boss, rng)
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
    if finale_open(state) is not None:  # M23.9: no new danger while the finale card is open
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
        boss_spawn = MonsterSpawn(
            monster=boss.archetype_id,
            zone_id=foes,
            name=boss.name,
            npc_id=boss.id,
            hp_scale=boss_hp_scale(state, data, boss.archetype_id),
        )
        spawns.insert(0, boss_spawn)
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
    region = region_of(state, offer.node_id)
    if boss is not None and region is not None and "boss_surprised" in route_effects(state, region):
        surprise = SurpriseKind.HOSTILE
    setup = _setup(state, offer, data, rng, surprise)
    events.extend(start_encounter(rng, state, setup, data.monsters))
    return events
