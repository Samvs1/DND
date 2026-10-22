"""Executors for `request_check` and `request_save` (SPEC 6.3): tier -> DC via `rules.checks`.

Every result carries its DC tier (`CheckResult.tier`, the dice show's difficulty word). Every
roll goes through the condition-aware rules functions and is logged as a `CheckResolved`
event; consequences are separate tool calls. A search check (Perception, Investigation, WIS or
INT) also discovers hidden features (M4.3) and hidden items (M23.3) of the current place whose
DC the total meets (`aidm.rules.scene.discovery_events`). Out of a fight in a dark unlit place a
search check rolls at disadvantage, whatever the AI asked (`aidm.rules.light.sight_darkness`,
M27.2: *Darkness* in `adv_why`); darkness never raises a DC, so nothing is hidden outright.
The hero's gear boons apply by themselves, named in `adv_why` (M27.3,
`aidm.rules.gear_checks.gear_check`, which also applies the proficiency of a tool in use).
A check naming a LOCKED feature here (`feature`, M27.4) is a lock check
(`aidm.rules.locks.lock_check`): a fitting key opens it with no roll, Athletics/STR forces it
(noisy), Sleight of Hand/DEX picks it with the hero's thieves' tools, at the lock's own tier
(the AI's tier and advantage do not apply); any other check is refused until it is open.

Public API: `run_request_check(state, args, ctx, rng, regs)`,
`run_request_save(state, args, ctx, rng, regs)` -> `ToolResult`.
"""

from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import require_creature
from aidm.dm.tools import RequestCheckArgs, RequestSaveArgs
from aidm.models.abilities import Skill
from aidm.models.checks import CheckResult
from aidm.models.dice import AdvState
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.item_events import FeatureUnlocked, PlaceAlerted
from aidm.models.state import Creature, GameState
from aidm.models.world_events import FeatureDiscovered
from aidm.rules.checks import dc_for_tier
from aidm.rules.conditions import save_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.gear_checks import gear_check
from aidm.rules.locks import lock_check, locked_here
from aidm.rules.scene import discovery_events


def _outcome(name: str, label: str, result: CheckResult) -> str:
    verdict = "success" if result.success else "failure"
    return f"{name} {label}: {result.roll.total} vs DC {result.dc} -> {verdict}"


def _lock_summary(state: GameState, creature: Creature, events: list[AnyEvent]) -> str:
    parts: list[str] = []
    for event in events:
        if isinstance(event, CheckResolved):
            label = event.result.skill or event.result.ability
            parts.append(_outcome(creature.name, f"{label} check on the lock", event.result))
        elif isinstance(event, FeatureUnlocked):
            how = f"with the {event.item}" if event.method == "key" else f"({event.method})"
            parts.append(f"unlocked {state.world.features[event.feature_id].name} {how}")
        elif isinstance(event, PlaceAlerted):
            parts.append("the noise alerted this place")
    return "; ".join(parts)


def _on_lock(
    state: GameState, args: RequestCheckArgs, creature: Creature, rng: Rng
) -> ToolResult | None:
    feature = locked_here(state, args.feature)
    if isinstance(feature, str):
        return None
    outcome = lock_check(rng, state, creature, feature, args.ability_or_skill, args.reason)
    if isinstance(outcome, str):
        raise ToolRefused(outcome)
    return ToolResult(events=tuple(outcome), summary=_lock_summary(state, creature, outcome))


def run_request_check(
    state: GameState, args: RequestCheckArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    creature = require_creature(state, args.actor)
    on_lock = _on_lock(state, args, creature, rng) if args.feature else None
    if on_lock is not None:
        return on_lock
    dc = dc_for_tier(args.dc_tier)
    adv = int(args.advantage is AdvState.ADVANTAGE)
    dis = int(args.advantage is AdvState.DISADVANTAGE)
    what = args.ability_or_skill
    result = gear_check(rng, state, creature, what, dc, adv_sources=adv, dis_sources=dis)
    label = f"{what.value} check" if isinstance(what, Skill) else f"{what.value.upper()} check"
    result = result.model_copy(update={"tier": args.dc_tier})
    event = CheckResolved(creature_id=creature.id, result=result, reason=args.reason)
    found = discovery_events(state, creature.id, result)
    summary = _outcome(creature.name, label, result)
    names = [
        state.world.features[e.feature_id].name
        if isinstance(e, FeatureDiscovered)
        else state.world.items[e.item_id].name
        for e in found
    ]
    if names:
        summary += f"; discovered: {', '.join(names)}"
    return ToolResult(events=(event, *found), summary=summary)


def run_request_save(
    state: GameState, args: RequestSaveArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    creatures = [require_creature(state, cid) for cid in dict.fromkeys(args.actors)]
    dc = dc_for_tier(args.dc_tier)
    events: list[AnyEvent] = []
    lines: list[str] = []
    for creature in creatures:
        result = save_with_conditions(rng, creature, args.ability, dc)
        result = result.model_copy(update={"tier": args.dc_tier})
        events.append(CheckResolved(creature_id=creature.id, result=result, reason=args.reason))
        lines.append(_outcome(creature.name, f"{args.ability.value.upper()} save", result))
    return ToolResult(events=tuple(events), summary="; ".join(lines))
