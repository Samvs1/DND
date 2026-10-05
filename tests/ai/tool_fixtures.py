"""Fixtures for the DM tool executor tests: a level-1 party in a small world graph."""

import random
from typing import Any

from aidm.dm.llm_types import ToolCall
from aidm.dm.tool_context import ToolContext, ToolResult, tool_registries
from aidm.dm.tool_exec import execute_tool
from aidm.dm.tools import dm_tool
from aidm.models.state import GameState
from aidm.models.world import NpcSecret, WorldNpc
from aidm.models.world_events import NpcIntroduced
from aidm.session.reducer import apply
from tests.sim.sim_setup import build_party

REGS = tool_registries()
ACTOR = ToolContext(actor_id="fighter")


def party_state(level: int = 1) -> GameState:
    state = GameState(campaign_id="tools", seed=7)
    build_party(state, level)
    world = state.world
    world.current_node = "town"
    world.visited = ["town"]
    world.neighbours = {"town": ["forest", "crypt"], "forest": ["town"], "crypt": ["town"]}
    world.locked_nodes = ["crypt"]
    return state


def tool_call(tool: str, /, **args: Any) -> ToolCall:
    return ToolCall("call_0", tool, dm_tool(tool).args_model.model_validate(args))


def run_tool(
    state: GameState, tool: str, /, *, ctx: ToolContext = ACTOR, seed: int = 1, **args: Any
) -> ToolResult:
    return execute_tool(state, tool_call(tool, **args), ctx, random.Random(seed), REGS)


def apply_result(state: GameState, result: ToolResult) -> GameState:
    for event in result.events:
        apply(state, event)
    return state


def add_npc(
    state: GameState,
    npc_id: str = "npc-mira",
    *,
    name: str = "Mira",
    archetype: str = "commoner",
    secrets: tuple[NpcSecret, ...] = (),
    **fields: Any,
) -> WorldNpc:
    fields.setdefault("node_id", state.world.current_node)
    npc = WorldNpc(
        id=npc_id,
        name=name,
        role="innkeeper",
        archetype_id=archetype,
        secrets=list(secrets),
        **fields,
    )
    apply(state, NpcIntroduced(npc=npc))
    return state.world.npcs[npc_id]
