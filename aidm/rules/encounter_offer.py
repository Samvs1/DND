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
M29.6b area danger (`aidm.rules.encounter_danger`): the offer's difficulty word is the higher of
the XP rating and each monster's area-blast rating against the heroes' hit points; a spoke never
picks a monster whose blast alone rates above the spoke cap (unless nothing else exists), and a
master whose blast rates above the boss cap comes without company.
M29.7d: the word also counts each foe's expected damage per round and a shooter's cover
(`rules.offer_label`); the fight map is fixed by the seed, the node and the offer id
(`fight_map`), so the card already knows the zone the foes stand in.

M31.1d: the registries (`OfferData`) and the spoke pick live in `rules.offer_spokes`; the
master's hit points, master's turn, trait and rated XP come from `rules.master_boost` (the
master template), so the offer's word and the spawned master agree.

Public API:
- `fight_map(state, node, offer_id, terrains) -> ZoneMap`: the offer's fight map.
- `arrival_offer_events(state, data, retreat_node) -> list[AnyEvent]`: `[EncounterOffered]` or [].
- `offer_fight_events(state, offer, data, rng, surprise, extra=()) -> list[AnyEvent]`: the boss
  turns hostile if needed, then `rules.encounter.start_encounter` on a zone map from the node
  terrain. M31.1b V10: `extra` are the other people the party attacked (they stand next to the
  heroes, as in `dm.tool_exec_rewards`); the caller turns them hostile.
"""

import random
from collections.abc import Sequence

from aidm.data.registry import Registry
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
from aidm.models.zones import ZoneMap
from aidm.rules.checks import dc_for_tier
from aidm.rules.dice import Rng
from aidm.rules.dm_tiers import party_levels
from aidm.rules.encounter import start_encounter
from aidm.rules.encounter_budget import adjusted_xp, rate_encounter
from aidm.rules.finale import finale_open
from aidm.rules.master_boost import MasterBoost, boss_cap_xp, master_boost
from aidm.rules.offer_label import LabelContext, danger_label, heroes_ac
from aidm.rules.offer_spokes import OfferData, hero_hp, safe_monsters, spoke_monsters, xp_of
from aidm.rules.progression import boss_defeated, boss_npc, node_plan, region_of
from aidm.rules.quest_progress import route_effects
from aidm.rules.social import attitude_band, attitude_score, hostile_attitude_events
from aidm.rules.zone_gen import generate_zone_map
from aidm.rules.zones import zone_neighbors


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
        xps = [xp_of(data, m) for m in picked]
        fits = [m for m in pool if adjusted_xp([*xps, xp_of(data, m)], size, data.tables) <= budget]
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


def _monsters(
    state: GameState,
    data: OfferData,
    where: tuple[RegionPlan, NodePlan],
    boss: WorldNpc | None,
    rng: Rng,
) -> list[str]:
    region, node = where
    if boss is None:
        return spoke_monsters(state, data, region, node, rng)
    levels = party_levels(state)
    rating = Difficulty(data.tables.boss_rating_cap)
    cap = boss_cap_xp(levels, data, region.tier)
    alone = not safe_monsters(state, data, [boss.archetype_id], rating)
    if alone or "boss_alone" in route_effects(state, region):
        return []
    themes = tuple(safe_monsters(state, data, list(_boss_themes(region, node)), rating))
    return _company(rng, data, themes, cap, [boss.archetype_id], len(levels))[1:]


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
    xps = [xp_of(data, m) for m in monsters]
    boost = MasterBoost()
    if boss is not None:
        boost = master_boost(state, data, boss.archetype_id, region)
        xps.append(round(xp_of(data, boss.archetype_id) * boost.rating_factor))
    rated = rate_encounter(xps, party_levels(state), data.tables)
    offer_id = f"offer-{state.event_count}"
    zone_map = fight_map(state, node, offer_id, data.terrains)
    cover = zone_map.zone(_foes_zone(zone_map)).cover
    ctx = LabelContext(
        data.tables, data.overlay, data.spells, hero_hp(state), heroes_ac(state), cover
    )
    foes = [data.monsters.get(m) for m in [*monsters, *([boss.archetype_id] if boss else [])]]
    extra = [0.0] * len(monsters) + ([boost.extra_attacks] if boss else [])
    rated = danger_label(rated, foes, ctx, extra)
    common = _dc(data.tiers.offer_dc_tiers, region.tier)
    parley = _dc(data.tiers.boss_parley_dc_tiers, region.tier) if boss else common
    return EncounterOffer(
        id=offer_id,
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


def fight_map(
    state: GameState, node: NodePlan | None, offer_id: str, terrains: Registry[TerrainTemplate]
) -> ZoneMap:
    """The fight's zone map, fixed by the campaign seed, the node and the offer (M29.7d: the
    warning card knows the foes' cover before the fight starts)."""
    campaign = state.campaign
    seed = campaign.seed if campaign is not None else state.seed
    node_id = node.id if node is not None else ""
    tags = node.terrain_tags if node is not None else ()
    return generate_zone_map(random.Random(f"{seed}:{node_id}:{offer_id}:map"), tags, terrains)


def _foes_zone(zone_map: ZoneMap) -> str:
    return zone_neighbors(zone_map, zone_map.zones[0].id)[0][0]


def _setup(
    state: GameState,
    offer: EncounterOffer,
    data: OfferData,
    surprise: SurpriseKind,
    extra: Sequence[WorldNpc],
) -> EncounterSetup:
    zone_map = fight_map(state, node_plan(state, offer.node_id), offer.id, data.terrains)
    start = zone_map.zones[0].id
    foes = _foes_zone(zone_map)
    spawns = [MonsterSpawn(monster=m, zone_id=foes) for m in offer.monster_ids]
    spawns += [
        MonsterSpawn(monster=n.archetype_id, zone_id=start, name=n.name, npc_id=n.id)
        for n in extra
        if n.id != offer.boss_npc_id
    ]
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if boss is not None:
        boost = master_boost(state, data, boss.archetype_id, region_of(state, offer.node_id))
        boss_spawn = MonsterSpawn(
            monster=boss.archetype_id,
            zone_id=foes,
            name=boss.name,
            npc_id=boss.id,
            hp_scale=boost.hp_scale,
            legendary_points=boost.legendary_points,
            legendary_recharge=boost.legendary_recharge,
            traits=boost.traits,
        )
        spawns.insert(0, boss_spawn)
    pcs = sorted(c.id for c in state.creatures.values() if c.pc is not None and not c.dead)
    return EncounterSetup(
        encounter_id=f"enc-{state.event_count}",
        zone_map=zone_map,
        party=tuple(PartyPlacement(creature_id=pc, zone_id=start) for pc in pcs),
        monsters=tuple(spawns),
        surprise=surprise,
        offer_id=offer.id,
    )


def offer_fight_events(
    state: GameState,
    offer: EncounterOffer,
    data: OfferData,
    rng: Rng,
    surprise: SurpriseKind,
    extra: Sequence[WorldNpc] = (),
) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if boss is not None and not boss.hostile:
        events.extend(hostile_attitude_events(boss, "the party fights them"))
    region = region_of(state, offer.node_id)
    if boss is not None and region is not None and "boss_surprised" in route_effects(state, region):
        surprise = SurpriseKind.HOSTILE
    setup = _setup(state, offer, data, surprise, extra)
    events.extend(start_encounter(rng, state, setup, data.monsters))
    return events
