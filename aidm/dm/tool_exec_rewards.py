"""Executors for `grant_item`, `grant_xp` and `start_encounter` (SPEC 6.3, 6.7, 9).

Rewards come only from capped tiers: items from the catalogue (SRD equipment with a cost, plus
data/bg3/consumables.json with a value) whose total value fits the region tier's cap, XP from the
party-level table. Fights use encounter-ready catalogue monsters within the region tier and the
CR budget (`rules.encounter_budget.check_encounter_budget`: never above deadly). Fighting a
non-hostile NPC stops at the point of no return until the player confirms.

Public API: `run_grant_item`, `run_grant_xp`, `run_start_encounter` -> `ToolResult`;
`catalog_value_gp(regs, catalog_id) -> float | None` (None: not a grantable catalogue item).
"""

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
from aidm.models.encounter import EncounterSetup, EncounterStatus, MonsterSpawn, PartyPlacement
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.rules.dice import Rng
from aidm.rules.dm_tiers import item_value_cap, party_level, party_levels, xp_award
from aidm.rules.encounter import EncounterRefused, start_encounter
from aidm.rules.encounter_budget import check_encounter_budget
from aidm.rules.leveling import gain_xp
from aidm.rules.social import hostile_attitude_events
from aidm.rules.zone_gen import generate_zone_map
from aidm.rules.zones import zone_neighbors

GP_PER_UNIT = {"cp": 0.01, "sp": 0.1, "ep": 0.5, "gp": 1.0, "pp": 10.0}


def catalog_value_gp(regs: ToolRegistries, catalog_id: str) -> float | None:
    consumable = regs.combat.consumables.find(catalog_id)
    if consumable is not None:
        return None if consumable.value_gp is None else float(consumable.value_gp)
    item = regs.combat.chars.equipment.find(catalog_id)
    if item is None or item.cost is None or item.cost.unit not in GP_PER_UNIT:
        return None
    return item.cost.quantity * GP_PER_UNIT[item.cost.unit]


def run_grant_item(
    state: GameState, args: GrantItemArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    unit = catalog_value_gp(regs, args.catalog_id)
    if unit is None:
        raise ToolRefused(f"{args.catalog_id!r} is not a catalogue item")
    if args.qty > regs.tiers.max_item_qty:
        raise ToolRefused(f"at most {regs.tiers.max_item_qty} items per grant")
    cap = item_value_cap(regs.tiers, state.world.region_tier)
    if unit * args.qty > cap:
        raise ToolRefused(f"worth {unit * args.qty:g} gp, above this region's cap of {cap} gp")
    pc = recipient_pc(state, ctx)
    inventory = pc.pc.inventory if pc.pc is not None else []
    held = next((i.qty for i in inventory if i.item == args.catalog_id), 0)
    event = InventoryChanged(
        creature_id=pc.id, item=args.catalog_id, delta=args.qty, qty=held + args.qty
    )
    return ToolResult(events=(event,), summary=f"{pc.name} gains {args.qty} x {args.catalog_id}")


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
    spawns += [MonsterSpawn(monster=n.archetype_id, zone_id=foes_zone, name=n.name) for n in npcs]
    return EncounterSetup(
        encounter_id=f"enc-{state.event_count}",
        zone_map=zone_map,
        party=tuple(PartyPlacement(creature_id=pc.id, zone_id=start) for pc in living_pcs(state)),
        monsters=tuple(spawns),
        surprise=args.surprise,
    )


def run_start_encounter(
    state: GameState, args: StartEncounterArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    if state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE:
        raise ToolRefused("a fight is already under way")
    _check_monsters(state, args, regs)
    npcs = _foes(state, args)
    difficulty = _check_budget(state, [*args.monster_ids, *(n.archetype_id for n in npcs)], regs)
    peaceful = non_hostile(npcs)
    if peaceful and not ctx.confirm_hostile:
        return hostile_pending(ctx, peaceful, "start_encounter")
    events: list[AnyEvent] = []
    for npc in peaceful:
        events.extend(hostile_attitude_events(npc, "the party attacked"))
    try:
        events.extend(
            start_encounter(rng, state, _setup(state, args, npcs, rng, regs), regs.combat.monsters)
        )
    except EncounterRefused as exc:
        raise ToolRefused(str(exc)) from None
    names = ", ".join([*args.monster_ids, *(n.name for n in npcs)])
    return ToolResult(events=tuple(events), summary=f"fight starts ({difficulty}): {names}")
