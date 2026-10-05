"""Shared lookups for the DM tool executors: every failed lookup is a `ToolRefused`.

Public API:
- `require_creature(state, creature_id, *, alive=True) -> Creature`.
- `require_npc(state, npc_id) -> WorldNpc`; `npc_is_present(state, npc) -> bool` (at the
  party's node; with no world graph yet every NPC is present).
- `new_entity_id(prefix, name, taken) -> str`: `<prefix>-<slug>` with `-2`, `-3`... on clashes.
- `hostile_pending(ctx, npcs, tool) -> ToolResult`: the point-of-no-return stop: a
  `HostileActPending` log event plus the `PendingConfirmation` (nothing else happens).
- `non_hostile(npcs) -> list[WorldNpc]`.
- `living_pcs(state) -> list[Creature]`; `recipient_pc(state, ctx) -> Creature` (the acting PC,
  else the first living PC by id).
"""

import re
from collections.abc import Iterable, Sequence

from aidm.dm.tool_context import PendingConfirmation, ToolContext, ToolRefused, ToolResult
from aidm.models.state import Creature, GameState
from aidm.models.world import WorldNpc
from aidm.models.world_events import HostileActPending
from aidm.rules.social import npc_is_hostile


def require_creature(state: GameState, creature_id: str, *, alive: bool = True) -> Creature:
    creature = state.creatures.get(creature_id)
    if creature is None:
        raise ToolRefused(f"unknown creature {creature_id!r}")
    if alive and creature.dead:
        raise ToolRefused(f"{creature_id!r} is dead")
    return creature


def require_npc(state: GameState, npc_id: str) -> WorldNpc:
    npc = state.world.npcs.get(npc_id)
    if npc is None:
        raise ToolRefused(f"unknown npc {npc_id!r}; introduce_npc registers new NPCs")
    return npc


def npc_is_present(state: GameState, npc: WorldNpc) -> bool:
    return npc.node_id == state.world.current_node


def new_entity_id(prefix: str, name: str, taken: Iterable[str]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32] or "x"
    used = set(taken)
    base = f"{prefix}-{slug}"
    candidate, n = base, 2
    while candidate in used:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def non_hostile(npcs: Sequence[WorldNpc]) -> list[WorldNpc]:
    return [npc for npc in npcs if not npc_is_hostile(npc)]


def hostile_pending(ctx: ToolContext, npcs: Sequence[WorldNpc], tool: str) -> ToolResult:
    ids = tuple(n.id for n in npcs)
    names = ", ".join(n.name for n in npcs)
    prompt = f"Attacking {names} is a point of no return: they will fight back. Confirm?"
    event = HostileActPending(actor_id=ctx.actor_id, npc_ids=ids, tool=tool, reason=prompt)
    pending = PendingConfirmation(ctx.actor_id, ids, tool, prompt)
    summary = f"waiting for the player to confirm a hostile act against {names}"
    return ToolResult(events=(event,), summary=summary, pending=pending)


def living_pcs(state: GameState) -> list[Creature]:
    pcs = [c for c in state.creatures.values() if c.pc is not None and not c.dead]
    return sorted(pcs, key=lambda c: c.id)


def recipient_pc(state: GameState, ctx: ToolContext) -> Creature:
    if ctx.actor_id is not None:
        actor = state.creatures.get(ctx.actor_id)
        if actor is not None and actor.pc is not None and not actor.dead:
            return actor
    pcs = living_pcs(state)
    if not pcs:
        raise ToolRefused("no living player character to receive it")
    return pcs[0]
