"""Executors for the world tools (SPEC 2.2 closed world, 6.3, 9).

`introduce_npc` / `introduce_feature` are the only ways new people and features exist (capped
per scene, NPC stat blocks from the SRD catalogue). A feature's lock (M27.4) is repaired, never
refused: `aidm.rules.locks.placed_lock` strips a lock that may not stay and caps its tier, and
(M29.6b) a new lock's tier is at most the region tier's `dm_tiers.check_dc_tier_cap`.
`move_party` only follows `legal_neighbours`
(the campaign graph minus the derived locks) and never moves while an encounter offer waits;
leaving a region with open tasks first asks (M23.4, `rules.quest_leaving.crossing`): the same
point-of-no-return `pending` as a hostile act, executed again with `confirm_hostile` on yes.
After `PartyMoved` come `aidm.rules.light.arrival_events` (a carried light alerts a dark place).
Attitude goes through `aidm.rules.social` (bounded). Quests and facts: `aidm.dm.tool_exec_ledger`.

Public API: `run_update_attitude`, `run_reveal_secret`, `run_move_party`, `run_introduce_npc`,
`run_introduce_feature`, `run_open_shop`, each
`(state, args, ctx, rng, regs) -> ToolResult`.
"""

from aidm.dm.tool_context import (
    PendingConfirmation,
    ToolContext,
    ToolRefused,
    ToolRegistries,
    ToolResult,
)
from aidm.dm.tool_exec_common import new_entity_id, npc_is_present, require_npc
from aidm.dm.tools import (
    IntroduceFeatureArgs,
    IntroduceNpcArgs,
    MovePartyArgs,
    OpenShopArgs,
    RevealSecretArgs,
    UpdateAttitudeArgs,
)
from aidm.models.checks import DcTier
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState
from aidm.models.world import FeatureKind, LockInfo, WorldFeature, WorldNpc
from aidm.models.world_events import (
    FeatureIntroduced,
    NpcIntroduced,
    PartyMoved,
    SecretRevealed,
    ShopOpened,
)
from aidm.rules.checks import dc_for_tier, difficulty_word
from aidm.rules.dice import Rng
from aidm.rules.dm_tiers import capped_dc_tier
from aidm.rules.gateway_lock import locked_reason
from aidm.rules.light import arrival_events
from aidm.rules.locks import lock_problem, placed_lock
from aidm.rules.projection import project_state
from aidm.rules.quest_leaving import crossing, crossing_prompt
from aidm.rules.secrets import reveal_refusal
from aidm.rules.shop import npc_shop_stock
from aidm.rules.social import (
    attitude_band,
    attitude_score,
    npc_is_hostile,
    social_attitude_events,
)
from aidm.rules.world_graph import legal_neighbours


def _present_npc(state: GameState, npc_id: str) -> WorldNpc:
    npc = require_npc(state, npc_id)
    if not npc_is_present(state, npc):
        raise ToolRefused(f"{npc.name} is not here")
    return npc


def run_update_attitude(
    state: GameState, args: UpdateAttitudeArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    npc = _present_npc(state, args.npc)
    events = social_attitude_events(npc, args.delta_tier, args.reason)
    after = project_state(state, events).world.npcs[npc.id]
    band = attitude_band(attitude_score(after))
    return ToolResult(events=tuple(events), summary=f"{npc.name} is now {band.value}")


def run_reveal_secret(
    state: GameState, args: RevealSecretArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    npc = _present_npc(state, args.npc)
    refusal = reveal_refusal(state, npc, args.secret_id)
    if refusal is not None:
        raise ToolRefused(refusal)
    secret = next(s for s in npc.secrets if s.id == args.secret_id)
    event = SecretRevealed(npc_id=npc.id, secret_id=secret.id)
    return ToolResult(events=(event,), summary=f"{npc.name} reveals: {secret.text}")


def run_move_party(
    state: GameState, args: MovePartyArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    world = state.world
    if state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE:
        raise ToolRefused("the party cannot travel during a fight")
    if state.campaign is not None and state.campaign.offer is not None:
        raise ToolRefused("something blocks the way: fight, sneak past, escape or parley first")
    if args.node_id not in world.neighbours.get(world.current_node or "", []):
        listed = ", ".join(legal_neighbours(world, world.current_node)) or "none"
        raise ToolRefused(f"{args.node_id!r} is not a neighbour; legal exits: {listed}")
    if args.node_id not in legal_neighbours(world, world.current_node):
        why = locked_reason(state, args.node_id) or "it is barred"
        raise ToolRefused(f"the way to {args.node_id!r} is still barred: {why}")
    cross = None if ctx.confirm_hostile else crossing(state, args.node_id)
    if cross is not None:
        prompt = crossing_prompt(cross)
        pending = PendingConfirmation(ctx.actor_id, (), "move_party", prompt)
        summary = "waiting for the party to agree to leave open tasks behind"
        return ToolResult(summary=summary, pending=pending)
    event = PartyMoved(
        from_node=world.current_node, to_node=args.node_id, scene_index=world.scene_index + 1
    )
    arrival = arrival_events(state, args.node_id)  # a carried light gives a dark place away
    return ToolResult(events=(event, *arrival), summary=f"the party travels to {args.node_id}")


def _scene_count(entities: list[WorldNpc] | list[WorldFeature], scene: int) -> int:
    return sum(1 for e in entities if e.scene_index == scene)


def run_introduce_npc(
    state: GameState, args: IntroduceNpcArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    world = state.world
    if args.archetype_id not in regs.combat.monsters:
        raise ToolRefused(f"unknown archetype {args.archetype_id!r}; use an SRD stat block id")
    if _scene_count(list(world.npcs.values()), world.scene_index) >= regs.tiers.max_npcs_per_scene:
        raise ToolRefused("this scene already has the most new NPCs allowed")
    taken = {n.name.lower() for n in world.npcs.values()}
    taken |= {c.name.lower() for c in state.creatures.values()}
    if args.name.lower() in taken:
        raise ToolRefused(f"{args.name!r} already exists; refer to them by id")
    npc = WorldNpc(
        id=new_entity_id("npc", args.name, world.npcs),
        name=args.name,
        role=args.role,
        archetype_id=args.archetype_id,
        demeanor=args.demeanor,
        voice_tag=args.voice_tag,
        node_id=world.current_node,
        scene_index=world.scene_index,
    )
    return ToolResult(events=(NpcIntroduced(npc=npc),), summary=f"npc {npc.name} id={npc.id}")


def _lock(
    state: GameState, tier: DcTier | None, kind: FeatureKind, regs: ToolRegistries
) -> LockInfo | None:
    if tier is None:
        return None
    return LockInfo(dc_tier=capped_dc_tier(regs.tiers, tier, state.world.region_tier), opens=kind)


def run_introduce_feature(
    state: GameState, args: IntroduceFeatureArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    world = state.world
    features = list(world.features.values())
    if _scene_count(features, world.scene_index) >= regs.tiers.max_features_per_scene:
        raise ToolRefused("this scene already has the most new features allowed")
    dc = dc_for_tier(args.discover_dc_tier) if args.discover_dc_tier is not None else None
    feature = WorldFeature(
        id=new_entity_id("feat", args.name, world.features),
        kind=args.kind,
        name=args.name,
        description=args.description,
        interactable=args.interactable,
        node_id=world.current_node,
        scene_index=world.scene_index,
        hidden=args.hidden,
        discover_dc=dc if args.hidden else None,
        lock=_lock(state, args.lock_tier, args.kind, regs),
    )
    placed = placed_lock(state, feature)
    summary = f"{feature.kind.value} {feature.name} id={feature.id}"
    if args.hidden:
        summary += f" (hidden, DC {dc})"
    if placed.lock is not None:
        summary += f" (locked, {difficulty_word(placed.lock.dc_tier)})"
    elif feature.lock is not None:
        summary += f" (no lock: {lock_problem(state, feature)})"
    feature = placed
    return ToolResult(events=(FeatureIntroduced(feature=feature),), summary=summary)


def run_open_shop(
    state: GameState, args: OpenShopArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    npc = _present_npc(state, args.npc)
    if npc_is_hostile(npc):
        raise ToolRefused(f"{npc.name} will not trade with the party")
    stock = npc_shop_stock(state, npc.id, regs.catalogue, regs.shops)
    shelves = ", ".join(f"{e.item} ({e.price_gp} gp)" for e in stock)
    return ToolResult(
        events=(ShopOpened(npc_id=npc.id),), summary=f"{npc.name} opens shop; stock: {shelves}"
    )
