"""Executors for `grant_item`, `grant_xp` and `start_encounter` (SPEC 6.3, 6.7, 9).

Rewards come only from capped tiers: items from the item catalogue
(`aidm.data.item_catalogue`: SRD gear, potions, camp supplies, keys, scrolls) whose total value fits
the region tier's cap (camp supplies go to the party pool), XP from the party-level table.
Fights use encounter-ready catalogue monsters within the region tier and the CR budget
(`rules.encounter_budget.check_encounter_budget`: never above deadly). Fighting a non-hostile
NPC stops at the point of no return until the player confirms. M27.5: an item that has uses
(data/bg3/item_uses.json: a torch, a rope, a scroll...) is never granted; such gear comes from
shops, loot and starting packs only (closes "I find a rope").

Public API: `run_grant_item`, `run_grant_xp`, `run_start_encounter` -> `ToolResult`;
`fight_npcs(state, npcs, rng, regs, why) -> ToolResult` (M29.7c R15: a confirmed attack on
people here starts the fight with them, no danger budget);
`catalog_value_gp(regs, catalog_id) -> float | None` (None: not a grantable catalogue item).
M31.1b V10: a fight started where an encounter offer still waits answers that offer with ALL its
foes (`rules.encounter_offer.offer_fight_events`: its monsters and its master), plus any other
person the party attacked; the model's own monster list is not used then (the offer owns the
foes), so a typed "I stab the zombie" never fields the zombie without the cultist.
"""

from aidm.data.item_uses import uses_for_item
from aidm.dm.arrival import offer_data
from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import (
    hostile_pending,
    living_pcs,
    non_hostile,
    npc_is_present,
    recipient_pc,
    require_npc,
)
from aidm.dm.tools import GrantItemArgs, GrantXpArgs, StartEncounterArgs
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.encounter import (
    EncounterSetup,
    EncounterStatus,
    MonsterSpawn,
    PartyPlacement,
    SurpriseKind,
)
from aidm.models.events import AnyEvent, CreatureAdded
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.rules.dice import Rng
from aidm.rules.dm_tiers import item_value_cap, party_level, party_levels, xp_award
from aidm.rules.encounter import EncounterRefused, start_encounter
from aidm.rules.encounter_budget import check_encounter_budget
from aidm.rules.encounter_offer import offer_fight_events
from aidm.rules.item_grants import gain_item_events
from aidm.rules.leveling import gain_xp
from aidm.rules.offer_answer import foes_gone
from aidm.rules.progression import node_plan, offer_closed
from aidm.rules.social import hostile_attitude_events
from aidm.rules.zone_gen import generate_zone_map
from aidm.rules.zones import zone_neighbors


def catalog_value_gp(regs: ToolRegistries, catalog_id: str) -> float | None:
    entry = regs.catalogue.find(catalog_id)
    return None if entry is None else entry.value_gp


def run_grant_item(
    state: GameState, args: GrantItemArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    unit = catalog_value_gp(regs, args.catalog_id)
    if unit is None:
        raise ToolRefused(f"{args.catalog_id!r} is not a catalogue item")
    found = regs.catalogue.find(args.catalog_id)
    if found is not None and uses_for_item(found.id):
        raise ToolRefused(
            f"{found.name} is usable gear: it comes only from shops, loot and starting packs;"
            " narrate that nothing of the kind turns up"
        )
    if args.qty > regs.tiers.max_item_qty:
        raise ToolRefused(f"at most {regs.tiers.max_item_qty} items per grant")
    cap = item_value_cap(regs.tiers, state.world.region_tier)
    if unit * args.qty > cap:
        raise ToolRefused(f"worth {unit * args.qty:g} gp, above this region's cap of {cap} gp")
    pc = recipient_pc(state, ctx)
    events = gain_item_events(state, [(pc.id, args.catalog_id, args.qty)], regs.catalogue)
    return ToolResult(
        events=tuple(events), summary=f"{pc.name} gains {args.qty} x {args.catalog_id}"
    )


def run_grant_xp(
    state: GameState, args: GrantXpArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    pcs = living_pcs(state)
    if not pcs:
        raise ToolRefused("no living player character to reward")
    amount = xp_award(regs.tiers, args.tier, party_level(state))
    events = [e for pc in pcs for e in gain_xp(pc, amount)]
    return ToolResult(events=tuple(events), summary=f"each hero gains {amount} XP")


def _check_monsters(state: GameState, args: StartEncounterArgs, regs: ToolRegistries) -> None:
    for mid in args.monster_ids:
        entry = regs.encounter_monsters.find(mid)
        if entry is None:
            raise ToolRefused(f"{mid!r} is not in the monster catalogue")
        if entry.tier > state.world.region_tier:
            raise ToolRefused(f"{mid!r} is too dangerous for this region")


def _foes(state: GameState, args: StartEncounterArgs) -> list[WorldNpc]:
    npcs = [require_npc(state, nid) for nid in dict.fromkeys(args.against_npcs)]
    for npc in npcs:
        if not npc_is_present(state, npc):
            raise ToolRefused(f"{npc.name} is not here")
    return npcs


def _check_budget(state: GameState, archetypes: list[str], regs: ToolRegistries) -> str:
    levels = party_levels(state)
    if not levels:
        raise ToolRefused("no living player character to fight")
    if len(archetypes) > regs.encounter_tables.max_monsters:
        raise ToolRefused(f"at most {regs.encounter_tables.max_monsters} foes per fight")
    xps = [regs.combat.monsters.get(a).xp for a in archetypes]
    budget = check_encounter_budget(xps, levels, regs.encounter_tables)
    if not budget.allowed:
        raise ToolRefused(
            f"too deadly: adjusted XP {budget.adjusted_xp} > budget {budget.deadly_budget}"
        )
    return budget.difficulty.value if budget.difficulty is not None else "trivial"


def _setup(
    state: GameState, args: StartEncounterArgs, npcs: list[WorldNpc], rng: Rng, regs: ToolRegistries
) -> EncounterSetup:
    zone_map = generate_zone_map(rng, args.terrain_tags, regs.terrains)
    start = zone_map.zones[0].id
    foes_zone = zone_neighbors(zone_map, start)[0][0]
    spawns = [MonsterSpawn(monster=m, zone_id=foes_zone) for m in args.monster_ids]
    # M19.2: an NPC the party was talking to stands right there (melee range), not a zone away.
    spawns += [
        MonsterSpawn(monster=n.archetype_id, zone_id=start, name=n.name, npc_id=n.id) for n in npcs
    ]
    return EncounterSetup(
        encounter_id=f"enc-{state.event_count}",
        zone_map=zone_map,
        party=tuple(PartyPlacement(creature_id=pc.id, zone_id=start) for pc in living_pcs(state)),
        monsters=tuple(spawns),
        surprise=args.surprise,
    )


def offer_here(state: GameState) -> EncounterOffer | None:
    """The encounter offer waiting at the party's place whose foes are still there (V10)."""
    offer = state.campaign.offer if state.campaign is not None else None
    if offer is None or offer.node_id != state.world.current_node or foes_gone(state, offer):
        return None
    return offer


def _answer_offer(
    state: GameState, offer: EncounterOffer, npcs: list[WorldNpc], rng: Rng, regs: ToolRegistries
) -> list[AnyEvent]:
    """M31.1b V10: the fight answers the waiting offer and fields every one of its foes."""
    events: list[AnyEvent] = [offer_closed(offer, OfferChoice.FIGHT, detail="the fight starts")]
    extra = [n for n in npcs if n.id != offer.boss_npc_id]
    for npc in non_hostile(extra):
        events.extend(hostile_attitude_events(npc, "the party attacked"))
    surprise = SurpriseKind.NONE
    events.extend(offer_fight_events(state, offer, offer_data(regs), rng, surprise, extra))
    return events


def _start(
    state: GameState,
    args: StartEncounterArgs,
    npcs: list[WorldNpc],
    rng: Rng,
    regs: ToolRegistries,
    why: str,
) -> list[AnyEvent]:
    offer = offer_here(state)
    try:
        if offer is not None:
            return _answer_offer(state, offer, npcs, rng, regs)
        events: list[AnyEvent] = []
        for npc in non_hostile(npcs):
            events.extend(hostile_attitude_events(npc, why))
        setup = _setup(state, args, npcs, rng, regs)
        events.extend(start_encounter(rng, state, setup, regs.combat.monsters))
    except EncounterRefused as exc:
        raise ToolRefused(str(exc)) from None
    return events


def _fielded(events: list[AnyEvent]) -> str:
    return ", ".join(e.creature.name for e in events if isinstance(e, CreatureAdded))


def fight_npcs(
    state: GameState, npcs: list[WorldNpc], rng: Rng, regs: ToolRegistries, why: str
) -> ToolResult:
    """M29.7c R15: the party's own confirmed attack on people standing here starts the fight
    with them at once (an ally master in the finale too). No danger budget: the point of no
    return was the warning, and refusing a possible attack is not the engine's call."""
    if state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE:
        raise ToolRefused("a fight is already under way")
    if not living_pcs(state):
        raise ToolRefused("no living player character to fight")
    node = node_plan(state, state.world.current_node)
    terrain = list(node.terrain_tags) if node is not None else []
    args = StartEncounterArgs(against_npcs=[n.id for n in npcs], terrain_tags=terrain)
    events = _start(state, args, npcs, rng, regs, why)
    fielded = _fielded(events)
    summary = f"the fight starts: {fielded}; the hero's blow is struck in the fight, by turns"
    return ToolResult(events=tuple(events), summary=summary)


def run_start_encounter(
    state: GameState, args: StartEncounterArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    if state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE:
        raise ToolRefused("a fight is already under way")
    npcs = _foes(state, args)
    difficulty = "the waiting encounter"
    if offer_here(state) is None:
        _check_monsters(state, args, regs)
        archetypes = [*args.monster_ids, *(n.archetype_id for n in npcs)]
        difficulty = _check_budget(state, archetypes, regs)
    peaceful = non_hostile(npcs)
    if peaceful and not ctx.confirm_hostile:
        return hostile_pending(ctx, peaceful, "start_encounter")
    events = _start(state, args, npcs, rng, regs, "the party attacked")
    summary = f"fight starts ({difficulty}): {_fielded(events)}"
    return ToolResult(events=tuple(events), summary=summary)
