"""The adjudicator: free-text action -> tool calls -> engine events (SPEC 6.1 steps 1-2, 6.2).

`adjudicate` builds the ADJUDICATE context pack, asks the model for tool calls and executes each
call through `aidm.dm.tool_exec.execute_tool`, applying its events through the caller's `apply`
callback BEFORE the next call (the callback must update `state` in place, as
`aidm.session.reducer.apply` does), so later calls see earlier effects. The model never mutates
anything.

Loop bounds: at most `MAX_ROUNDS` model calls; each round executes at most `MAX_CALLS_PER_ROUND`
calls (extra calls are dropped and audited). Rewards, fights, travel and social shifts are capped
per player action (`PER_ACTION_LIMITS`, M4.8): a repeated call beyond its cap is refused as a tool
error, so "call grant_xp major ten times" grants one tier at most. Results go back to the model
(assistant tool_calls + one `tool` message per call) only when it has something to react to: a
refused call (tool error, bounded by the round cap) or a check/save whose outcome decides the
consequences. Schema-invalid arguments never reach the engine: the LLM client retries them with
validator feedback.

Outcomes (never silent, never a dropped turn):
- zero tools or only `no_mechanics`: narration-only result;
- a point-of-no-return stop: `pending` + `pending_call` (the session asks the player and, on
  confirm, re-executes `pending_call` with `ToolContext(confirm_hostile=True)`); the loop stops;
- LLM failure: `fallback=True`, `failure` set, mechanics so far kept, an in-fiction `notice`;
- an empty or symbol-only action: no model call, a gentle `notice` (the turn still resolves).

Model role (`choose_role`): QUALITY when the scene is social (an NPC is present and the text
names them or their role, quotes speech, or uses a social verb) or complex (more than 40 words,
or chained steps: "then", "after that", ";"); FAST otherwise.

In combat, free text is a `creative_action` (`AdjudicationOptions.creative_action=True`): only
`CREATIVE_ACTION_TOOLS` are offered, so any other tool is rejected by the client validator.

Public API: `MAX_ROUNDS`, `MAX_CALLS_PER_ROUND`, `PER_ACTION_LIMITS`, `CREATIVE_ACTION_TOOLS`,
`EMPTY_NOTICE`, `FALLBACK_NOTICE`, `AdjudicationOptions`, `ResolvedCall`, `AdjudicationResult`,
`choose_role(state, text)`, `is_social_text(text)` (quoted speech or a social verb),
`adjudicate(state, actor_id, text, llm, ctx, rng, regs, apply)`.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from aidm.dm.context import DEFAULT_BUDGET_TOKENS, build_context, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.dm.entities import named_present_npcs
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmFailure, LlmRole, ToolCall, ToolCallResult
from aidm.dm.tool_context import PendingConfirmation, ToolContext, ToolRegistries, ToolResult
from aidm.dm.tool_exec import execute_tool
from aidm.dm.tools import DM_TOOLS, dm_tool
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.dice import Rng
from aidm.rules.scene import current_scene

MAX_ROUNDS = 3
MAX_CALLS_PER_ROUND = 5
MAX_ERROR_CHARS = 200
CREATIVE_ACTION_TOOLS = ("request_check", "request_save", "creative_effect", "no_mechanics")
FOLLOW_UP_TOOLS = frozenset({"request_check", "request_save"})
PER_ACTION_LIMITS = {
    "grant_xp": 1,
    "grant_item": 1,
    "start_encounter": 1,
    "move_party": 1,
    "update_attitude": 1,
    "reveal_secret": 1,
}
EMPTY_NOTICE = "You hesitate, and the moment passes quietly. What do you do?"
FALLBACK_NOTICE = "The world seems to hold its breath for a moment; nothing comes of it yet."

_SOCIAL = re.compile(
    r"\b(ask|asks|tell|tells|say|says|talk|talks|speak|speaks|persuade|convince|intimidate|"
    r"threaten|deceive|lie|bribe|negotiate|haggle|greet|plead|flatter|charm|chat)\b"
)
_CHAINED = re.compile(r"\bthen\b|\bafter that\b|;")
_MEANINGFUL = re.compile(r"[A-Za-z0-9]")

type ApplyFn = Callable[[AnyEvent], object]


@dataclass(frozen=True)
class AdjudicationOptions:
    events: Sequence[AnyEvent] = ()
    creative_action: bool = False
    confirm_hostile: bool = False
    budget_tokens: int = DEFAULT_BUDGET_TOKENS


@dataclass(frozen=True)
class ResolvedCall:
    round: int
    call: ToolCall
    result: ToolResult


@dataclass(frozen=True)
class AdjudicationResult:
    calls: tuple[ResolvedCall, ...] = ()
    events: tuple[AnyEvent, ...] = ()
    pending: PendingConfirmation | None = None
    pending_call: ToolCall | None = None
    fallback: bool = False
    failure: LlmFailure | None = None
    role: LlmRole = LlmRole.FAST
    rounds: int = 0
    notice: str | None = None
    audit: tuple[str, ...] = ()

    @property
    def executed(self) -> tuple[ResolvedCall, ...]:
        return tuple(r for r in self.calls if r.result.ok and r.call.name != "no_mechanics")

    @property
    def narration_only(self) -> bool:
        return not self.executed and self.pending is None


@dataclass
class _Run:
    role: LlmRole
    calls: list[ResolvedCall] = field(default_factory=list[ResolvedCall])
    events: list[AnyEvent] = field(default_factory=list[AnyEvent])
    audit: list[str] = field(default_factory=list[str])
    rounds: int = 0

    def finish(self, **extra: Any) -> AdjudicationResult:
        return AdjudicationResult(
            calls=tuple(self.calls),
            events=tuple(self.events),
            role=self.role,
            rounds=self.rounds,
            audit=tuple(self.audit),
            **extra,
        )


def is_social_text(text: str) -> bool:
    return '"' in text or _SOCIAL.search(text.lower()) is not None


def choose_role(state: GameState, text: str) -> LlmRole:
    lowered = text.lower()
    if current_scene(state).npc_ids and (named_present_npcs(state, text) or is_social_text(text)):
        return LlmRole.QUALITY
    if len(text.split()) > 40 or _CHAINED.search(lowered):
        return LlmRole.QUALITY
    return LlmRole.FAST


def _tool_message(resolved: ResolvedCall) -> dict[str, Any]:
    res = resolved.result
    if res.error is not None:
        reason = res.error[:MAX_ERROR_CHARS]
        text = f"ERROR: {reason} (nothing happened; fix the call or use another tool)"
    else:
        text = f"OK: {res.summary or 'done'}"
    return {"role": "tool", "tool_call_id": resolved.call.id, "content": text}


def _feedback(content: str, resolved: Sequence[ResolvedCall]) -> list[dict[str, Any]]:
    calls = [
        {
            "id": r.call.id,
            "type": "function",
            "function": {"name": r.call.name, "arguments": r.call.args.model_dump_json()},
        }
        for r in resolved
    ]
    assistant = {"role": "assistant", "content": content, "tool_calls": calls}
    return [assistant, *(_tool_message(r) for r in resolved)]


def _needs_follow_up(resolved: Sequence[ResolvedCall]) -> bool:
    return any(not r.result.ok or r.call.name in FOLLOW_UP_TOOLS for r in resolved)


def _limited(run: _Run, call: ToolCall) -> ToolResult | None:
    limit = PER_ACTION_LIMITS.get(call.name)
    used = sum(1 for r in run.calls if r.call.name == call.name and r.result.ok)
    if limit is None or used < limit:
        return None
    return ToolResult(error=f"at most {limit} {call.name} per player action")


def _execute_round(
    state: GameState,
    reply: ToolCallResult,
    run: _Run,
    tool_ctx: ToolContext,
    exec_args: tuple[Rng, ToolRegistries, ApplyFn],
) -> tuple[list[ResolvedCall], ResolvedCall | None]:
    rng, regs, apply = exec_args
    kept = reply.calls[:MAX_CALLS_PER_ROUND]
    if len(reply.calls) > len(kept):
        run.audit.append(f"round {run.rounds}: dropped {len(reply.calls) - len(kept)} extra calls")
    resolved: list[ResolvedCall] = []
    for call in kept:
        result = _limited(run, call) or execute_tool(state, call, tool_ctx, rng, regs)
        for event in result.events:
            apply(event)
            run.events.append(event)
        item = ResolvedCall(run.rounds, call, result)
        resolved.append(item)
        run.calls.append(item)
        verdict = "error" if result.error else ("pending" if result.pending else "ok")
        run.audit.append(f"round {run.rounds}: {call.name} {verdict}")
        if result.pending is not None:
            return resolved, item
    return resolved, None


async def adjudicate(
    state: GameState,
    actor_id: str,
    text: str,
    llm: LlmClient,
    ctx: AdjudicationOptions,
    rng: Rng,
    regs: ToolRegistries,
    apply: ApplyFn,
) -> AdjudicationResult:
    if not _MEANINGFUL.search(text):
        return AdjudicationResult(fallback=True, notice=EMPTY_NOTICE, audit=("empty action",))
    run = _Run(role=choose_role(state, text))
    names = CREATIVE_ACTION_TOOLS if ctx.creative_action else tuple(d.name for d in DM_TOOLS)
    tools = [dm_tool(n) for n in names]
    pack = build_context(
        state,
        ContextPurpose.ADJUDICATE,
        actor_id,
        text,
        events=ctx.events,
        budget_tokens=ctx.budget_tokens,
    )
    messages = to_messages(pack)
    tool_ctx = ToolContext(actor_id=actor_id, confirm_hostile=ctx.confirm_hostile)
    while run.rounds < MAX_ROUNDS:
        run.rounds += 1
        reply = await llm.call_tools(messages, tools, run.role, player_text=text)
        if isinstance(reply, LlmFailure):
            run.audit.append(f"round {run.rounds}: llm failure {reply.reason.value}")
            return run.finish(fallback=True, failure=reply, notice=FALLBACK_NOTICE)
        if all(c.name == "no_mechanics" for c in reply.calls):
            run.audit.append(f"round {run.rounds}: no mechanics")
            break
        resolved, stop = _execute_round(state, reply, run, tool_ctx, (rng, regs, apply))
        if stop is not None:
            return run.finish(pending=stop.result.pending, pending_call=stop.call)
        if not _needs_follow_up(resolved):
            break
        messages = [*messages, *_feedback(reply.content, resolved)]
    return run.finish()
