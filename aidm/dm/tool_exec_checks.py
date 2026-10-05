"""Executors for `request_check` and `request_save` (SPEC 6.3): tier -> DC via `rules.checks`.

Every roll goes through the condition-aware rules functions and is logged as a `CheckResolved`
event; consequences are separate tool calls.

Public API: `run_request_check(state, args, ctx, rng, regs)`,
`run_request_save(state, args, ctx, rng, regs)` -> `ToolResult`.
"""

from aidm.dm.tool_context import ToolContext, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import require_creature
from aidm.dm.tools import RequestCheckArgs, RequestSaveArgs
from aidm.models.abilities import Skill
from aidm.models.checks import CheckResult
from aidm.models.dice import AdvState
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.state import GameState
from aidm.rules.checks import dc_for_tier
from aidm.rules.conditions import (
    ability_check_with_conditions,
    save_with_conditions,
    skill_check_with_conditions,
)
from aidm.rules.dice import Rng


def _outcome(name: str, label: str, result: CheckResult) -> str:
    verdict = "success" if result.success else "failure"
    return f"{name} {label}: {result.roll.total} vs DC {result.dc} -> {verdict}"


def run_request_check(
    state: GameState, args: RequestCheckArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    creature = require_creature(state, args.actor)
    dc = dc_for_tier(args.dc_tier)
    adv = int(args.advantage is AdvState.ADVANTAGE)
    dis = int(args.advantage is AdvState.DISADVANTAGE)
    what = args.ability_or_skill
    if isinstance(what, Skill):
        result = skill_check_with_conditions(
            rng, creature, what, dc, adv_sources=adv, dis_sources=dis
        )
        label = f"{what.value} check"
    else:
        result = ability_check_with_conditions(
            rng, creature, what, dc, adv_sources=adv, dis_sources=dis
        )
        label = f"{what.value.upper()} check"
    event = CheckResolved(creature_id=creature.id, result=result, reason=args.reason)
    return ToolResult(events=(event,), summary=_outcome(creature.name, label, result))


def run_request_save(
    state: GameState, args: RequestSaveArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    creatures = [require_creature(state, cid) for cid in dict.fromkeys(args.actors)]
    dc = dc_for_tier(args.dc_tier)
    events: list[AnyEvent] = []
    lines: list[str] = []
    for creature in creatures:
        result = save_with_conditions(rng, creature, args.ability, dc)
        events.append(CheckResolved(creature_id=creature.id, result=result, reason=args.reason))
        lines.append(_outcome(creature.name, f"{args.ability.value.upper()} save", result))
    return ToolResult(events=tuple(events), summary="; ".join(lines))
