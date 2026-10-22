"""The `use_item` executor (M27.5, docs/next/GOAL_ITEMS.md "Design": the AI proposes, the engine
disposes).

`use_item(actor, item, target?)` runs THE interpreter (`aidm.rules.item_use.use_item`); with
`put_out` it puts out the hero's carried light (`aidm.rules.light.put_out`, free). Only the
acting hero uses their own gear. A refusal (`ItemUseRefused`, the only event then) comes back as
a tool error whose message tells the model what to narrate instead (an attempt, never a
result; pattern `FreeStepRefused`), and nothing is consumed. The summary states what the engine
resolved; a failed roll is told as an attempt ("the lock holds").

Public API: `run_use_item(state, args, ctx, rng, regs) -> ToolResult`,
`gear_summary(state, events) -> str`.
"""

from collections.abc import Sequence

from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import require_creature
from aidm.dm.tools import UseItemArgs
from aidm.models.events import AnyEvent, CampSuppliesChanged, CheckResolved, InventoryChanged
from aidm.models.item_events import (
    BoonGained,
    FeatureUnlocked,
    ItemUsed,
    ItemUseRefused,
    LightEnded,
    LightLit,
    PlaceAlerted,
    PlacesCharted,
)
from aidm.models.state import GameState
from aidm.rules.dice import Rng
from aidm.rules.item_effects import gear_name
from aidm.rules.item_use import use_item
from aidm.rules.light import put_out

ATTEMPT = "an attempt that changed nothing: tell it as tried, never as done"


def _who(state: GameState, creature_id: str) -> str:
    creature = state.creatures.get(creature_id)
    return creature.name if creature is not None else "someone"


def _check(state: GameState, event: CheckResolved) -> str:
    r = event.result
    label = r.skill or r.ability
    verdict = "success" if r.success else "failure"
    who = _who(state, event.creature_id)
    return f"{who} {label} check: {r.roll.total} vs DC {r.dc} -> {verdict}"


def _line(state: GameState, event: AnyEvent) -> str | None:
    match event:
        case ItemUsed():
            return f"{_who(state, event.creature_id)} uses the {gear_name(event.item).lower()}"
        case CheckResolved():
            return _check(state, event)
        case FeatureUnlocked():
            feature = state.world.features.get(event.feature_id)
            name = feature.name if feature is not None else "the lock"
            return f"{name} is unlocked ({event.method})"
        case LightLit():
            return f"{_who(state, event.creature_id)} carries a lit {gear_name(event.item).lower()}"
        case LightEnded():
            return f"{_who(state, event.creature_id)}'s light is put out"
        case BoonGained(boon=boon):
            skills = ", ".join((*boon.skills, *boon.saves_against))
            return f"{boon.name} gives advantage on {skills} (the engine applies it)"
        case PlaceAlerted():
            return "this place is alerted: foes here cannot be surprised"
        case PlacesCharted(nodes=nodes):
            return f"{len(nodes)} places charted on the map"
        case CampSuppliesChanged(delta=delta):
            return f"camp supplies {delta:+d}"
        case InventoryChanged(delta=delta):
            verb = "gains" if delta > 0 else "uses up"
            return f"{_who(state, event.creature_id)} {verb} {abs(delta)} {event.item}"
        case _:
            return None


def _still_locked(state: GameState, events: Sequence[AnyEvent]) -> str | None:
    opened = {e.feature_id for e in events if isinstance(e, FeatureUnlocked)}
    for event in events:
        if isinstance(event, ItemUsed) and event.target not in opened:
            feature = state.world.features.get(event.target or "")
            if feature is not None and feature.lock is not None:
                return f"the {feature.name} stays locked ({ATTEMPT})"
    return None


def gear_summary(state: GameState, events: Sequence[AnyEvent]) -> str:
    """Read with the state BEFORE the events apply (a lock tried is still on its feature)."""
    parts = [line for e in events if (line := _line(state, e))]
    held = _still_locked(state, events)
    return "; ".join([*parts, held] if held else parts) or "done"


def run_use_item(
    state: GameState, args: UseItemArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    actor = require_creature(state, args.actor)
    if ctx.actor_id is not None and actor.id != ctx.actor_id:
        raise ToolRefused(f"only the acting hero uses their own gear, not {actor.name}")
    if args.put_out:
        events = put_out(state, actor.id)
    else:
        events = use_item(state, actor.id, args.item, args.target, rng=rng)
    refusal = next((e for e in events if isinstance(e, ItemUseRefused)), None)
    if refusal is not None:
        raise ToolRefused(refusal.message)
    return ToolResult(events=tuple(events), summary=gear_summary(state, events))
