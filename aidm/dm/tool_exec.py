"""The ONE entry point that executes a validated DM tool call (SPEC 6.1 step 2, 6.3).

`execute_tool(state, call, ctx, rng, regs) -> ToolResult` never mutates `state`; the caller
applies `result.events` through the reducer (and must do so before executing the next call, so
each call sees the effects of the previous ones). A refusal (unknown id, cap, budget, illegal
move...) comes back as `ToolResult(error=...)` with no events, which the adjudicator returns to
the model as a tool error. A hostile act against a non-hostile NPC returns
`ToolResult(pending=...)` with only the `HostileActPending` log event until the player confirms
(`ToolContext.confirm_hostile`). Entity references are normalised first
(`aidm.dm.tool_refs.resolve_tool_refs`: a unique name such as "Aria" becomes its id).

Public API: `execute_tool`, `TOOL_EXECUTORS` (tool name -> (args model, executor)).
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from aidm.dm.llm_types import ToolCall
from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_checks import run_request_check, run_request_save
from aidm.dm.tool_exec_creative import run_creative_effect
from aidm.dm.tool_exec_items import run_give_keepsake, run_take_item
from aidm.dm.tool_exec_ledger import run_record_fact, run_update_quest
from aidm.dm.tool_exec_rewards import run_grant_item, run_grant_xp, run_start_encounter
from aidm.dm.tool_exec_world import (
    run_introduce_feature,
    run_introduce_npc,
    run_move_party,
    run_open_shop,
    run_reveal_secret,
    run_update_attitude,
)
from aidm.dm.tool_refs import resolve_tool_refs
from aidm.dm.tools import DM_TOOLS
from aidm.models.state import GameState
from aidm.rules.dice import Rng

type Executor = Callable[[GameState, Any, ToolContext, Rng, ToolRegistries], ToolResult]


def _no_mechanics(
    state: GameState, args: BaseModel, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    return ToolResult(summary="no mechanics; narrate only")


_RUNNERS: dict[str, Executor] = {
    "request_check": run_request_check,
    "request_save": run_request_save,
    "creative_effect": run_creative_effect,
    "update_attitude": run_update_attitude,
    "reveal_secret": run_reveal_secret,
    "move_party": run_move_party,
    "introduce_npc": run_introduce_npc,
    "introduce_feature": run_introduce_feature,
    "grant_item": run_grant_item,
    "grant_xp": run_grant_xp,
    "start_encounter": run_start_encounter,
    "open_shop": run_open_shop,
    "update_quest": run_update_quest,
    "record_fact": run_record_fact,
    "take_item": run_take_item,
    "give_keepsake": run_give_keepsake,
    "no_mechanics": _no_mechanics,
}

TOOL_EXECUTORS: dict[str, tuple[type[BaseModel], Executor]] = {
    d.name: (d.args_model, _RUNNERS[d.name]) for d in DM_TOOLS
}


def _args(call: ToolCall, model: type[BaseModel]) -> BaseModel:
    if isinstance(call.args, model):
        return call.args
    try:
        return model.model_validate(call.args.model_dump())
    except ValidationError as exc:
        raise ToolRefused(f"invalid arguments: {exc.errors()[0].get('msg', 'invalid')}") from None


def execute_tool(
    state: GameState, call: ToolCall, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    entry = TOOL_EXECUTORS.get(call.name)
    if entry is None:
        return ToolResult(error=f"unknown tool {call.name!r}")
    model, run = entry
    try:
        return run(state, resolve_tool_refs(state, _args(call, model)), ctx, rng, regs)
    except ToolRefused as exc:
        return ToolResult(error=exc.message)
