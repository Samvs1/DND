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
The scoped rope rule (M27.5, `aidm.rules.gear_fit`): when the player's words
(`ToolContext.player_text`) name gear the hero carries (`aidm.dm.gear_words.named_gear`, a
keepsake too) and the check is in a situation the item table covers (a lock, a dark place,
climbing, searching...) where none of that gear has a fitting use, the AI's advantage is
dropped (the plain check still rolls); elsewhere the AI's call stands.
M29.6b: a check's DC tier is at most the region tier's `dm_tiers.check_dc_tier_cap` (act 1:
medium), so an improvised gate never asks DC 20 of level-1 heroes; saves keep their tier.
M31.1a V9: a search check in a place where something is hidden rolls against the lowest DC of
what is hidden (`rules.scene.hidden_dc`), whatever tier the AI asked, so a failed search never
finds and a successful one always does (round 4: a 13 "failed" against DC 15 and found a DC 10
item).
M30.1: a check sent with `impossible` (the AI's "this cannot be done: <why>") rolls NO dice, so
no natural 20 rescues it; it returns one `ActionImpossible` event. A lock check still goes to the
lock rules first (a lock can always be forced or picked). `request_save` has no such option: a
save resists what happens to the creature, and a natural 20 never wins a save (DECISIONS M30.1).

Public API: `run_request_check(state, args, ctx, rng, regs)`,
`run_request_save(state, args, ctx, rng, regs)` -> `ToolResult`.
"""

from aidm.dm.gear_words import aims_at_lock, named_gear
from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import require_creature
from aidm.dm.tools import RequestCheckArgs, RequestSaveArgs
from aidm.models.abilities import Skill
from aidm.models.checks import CheckResult
from aidm.models.dice import AdvState
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.impossible import MAX_IMPOSSIBLE_TEXT, ActionImpossible
from aidm.models.item_events import FeatureUnlocked, PlaceAlerted
from aidm.models.state import Creature, GameState
from aidm.models.world_events import FeatureDiscovered
from aidm.rules.checks import dc_for_tier
from aidm.rules.conditions import save_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.dm_tiers import capped_dc_tier
from aidm.rules.gear_checks import gear_check
from aidm.rules.gear_fit import misfit
from aidm.rules.locks import lock_check, locked_here
from aidm.rules.scene import discovery_events, hidden_dc, is_search_check
from aidm.rules.searching import dc_tier


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
    if not any(isinstance(e, FeatureUnlocked) for e in events):
        parts.append("the lock holds: tell it as an attempt, it is still locked")
    return "; ".join(parts)


def _gear_misfit(
    state: GameState, args: RequestCheckArgs, creature: Creature, ctx: ToolContext
) -> bool:
    """The rope rule: the gear the player names has no use that fits this covered check."""
    named = named_gear(state, creature.id, ctx.player_text) if ctx.player_text else []
    if not named:
        return False
    locked = aims_at_lock(state, ctx.player_text, args.feature)
    return all(misfit(state, item, args.ability_or_skill, locked) for item in named)


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


def _impossible(
    creature: Creature, args: RequestCheckArgs, ctx: ToolContext, why: str
) -> ToolResult:
    text = (args.reason or ctx.player_text).strip()[:MAX_IMPOSSIBLE_TEXT]
    event = ActionImpossible(creature_id=creature.id, text=text, reason=why)
    summary = (
        f"{creature.name} cannot do this: {why}. No roll was made. Tell the attempt failing or"
        " never getting started, never as done; ask no other check for it."
    )
    return ToolResult(events=(event,), summary=summary)


def run_request_check(
    state: GameState, args: RequestCheckArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    creature = require_creature(state, args.actor)
    on_lock = _on_lock(state, args, creature, rng) if args.feature else None
    if on_lock is not None:
        return on_lock
    if args.impossible is not None and args.impossible.strip():
        return _impossible(creature, args, ctx, args.impossible.strip())
    tier = capped_dc_tier(regs.tiers, args.dc_tier, state.world.region_tier)
    dc = dc_for_tier(tier)
    hidden = hidden_dc(state) if is_search_check(args.ability_or_skill) else None
    if hidden is not None:  # M31.1a V9: a search where something is hidden rolls against its DC
        dc, tier = hidden, dc_tier(hidden) or tier
    adv = int(args.advantage is AdvState.ADVANTAGE)
    dropped = bool(adv) and _gear_misfit(state, args, creature, ctx)
    adv = 0 if dropped else adv
    dis = int(args.advantage is AdvState.DISADVANTAGE)
    what = args.ability_or_skill
    result = gear_check(rng, state, creature, what, dc, adv_sources=adv, dis_sources=dis)
    label = f"{what.value} check" if isinstance(what, Skill) else f"{what.value.upper()} check"
    result = result.model_copy(update={"tier": tier})
    event = CheckResolved(creature_id=creature.id, result=result, reason=args.reason)
    found = discovery_events(state, creature.id, result)
    summary = _outcome(creature.name, label, result)
    if dropped:
        summary += "; the gear named gives no help here (no advantage)"
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
