"""Executors for the world tools (SPEC 2.2 closed world, 6.3, 9).

`introduce_npc` / `introduce_feature` are the only ways new people and features exist (capped
per scene, NPC stat blocks from the SRD catalogue). `move_party` only follows the neighbour list
of the current node (the M5.2 region graph fills it) and never enters a locked node. Attitude goes
through `aidm.rules.social` (bounded). Quests and facts: `aidm.dm.tool_exec_ledger`.

Public API: `run_update_attitude`, `run_reveal_secret`, `run_move_party`, `run_introduce_npc`,
`run_introduce_feature`, `run_open_shop`, each
`(state, args, ctx, rng, regs) -> ToolResult`.
"""

from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import new_entity_id, npc_is_present, require_npc
from aidm.dm.tools import (
    IntroduceFeatureArgs,
    IntroduceNpcArgs,
    MovePartyArgs,
    OpenShopArgs,
    RevealSecretArgs,
    UpdateAttitudeArgs,
)
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState
from aidm.models.world import WorldFeature, WorldNpc
from aidm.models.world_events import (
    FeatureIntroduced,
    NpcIntroduced,
    PartyMoved,
    SecretRevealed,
    ShopOpened,
)
from aidm.rules.checks import dc_for_tier
from aidm.rules.dice import Rng
from aidm.rules.projection import project_state
from aidm.rules.social import (
    attitude_band,
    attitude_score,
    npc_is_hostile,
    social_attitude_events,
)


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
    secret = next((s for s in npc.secrets if s.id == args.secret_id), None)
    if secret is None or secret.revealed:
        raise ToolRefused(f"{npc.name} has no unrevealed secret {args.secret_id!r}")
    if secret.min_score is not None and attitude_score(npc) < secret.min_score:
        raise ToolRefused(f"{npc.name} does not trust the party enough to reveal that")
    event = SecretRevealed(npc_id=npc.id, secret_id=secret.id)
    return ToolResult(events=(event,), summary=f"{npc.name} reveals: {secret.text}")


def run_move_party(
    state: GameState, args: MovePartyArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    world = state.world
    if state.encounter is not None and state.encounter.status is EncounterStatus.ACTIVE:
        raise ToolRefused("the party cannot travel during a fight")
    legal = world.neighbours.get(world.current_node or "", [])
    if args.node_id not in legal:
        listed = ", ".join(legal) or "none"
        raise ToolRefused(f"{args.node_id!r} is not a neighbour; legal exits: {listed}")
    if args.node_id in world.locked_nodes:
        raise ToolRefused(f"the way to {args.node_id!r} is still barred")
    event = PartyMoved(
        from_node=world.current_node, to_node=args.node_id, scene_index=world.scene_index + 1
    )
    return ToolResult(events=(event,), summary=f"the party travels to {args.node_id}")


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
    )
    summary = f"{feature.kind.value} {feature.name} id={feature.id}"
    if args.hidden:
        summary += f" (hidden, DC {dc})"
    return ToolResult(events=(FeatureIntroduced(feature=feature),), summary=summary)


def run_open_shop(
    state: GameState, args: OpenShopArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    npc = _present_npc(state, args.npc)
    if npc_is_hostile(npc):
        raise ToolRefused(f"{npc.name} will not trade with the party")
    return ToolResult(events=(ShopOpened(npc_id=npc.id),), summary=f"{npc.name} opens shop")
