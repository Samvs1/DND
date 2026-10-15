"""Executors of the item tools (M19.3, owner playtest 2026-10-10: "I pick up the pouch" was only
narrated; nothing could pick up a world item, and story finds such as a note were never carried).

`take_item` moves a visible item lying at the current place to the acting hero through
`rules.equipment.take_events` (a catalogue item into the inventory, anything else as a
keepsake). `give_keepsake` hands the acting hero a found story object: a `Keepsake` with no
value, at most `MAX_KEEPSAKES` per hero. M23.3: a name that looks like an engine-placed quest
item (`rules.quest_items.quest_item_named`) never makes a lookalike: a copy lying visible here
is picked up for real (`take_events`, as `take_item`); one lying elsewhere, hidden, carried or
already handed over is refused as a tool error, so the model narrates something else.

Public API: `MAX_KEEPSAKES`, `run_take_item`, `run_give_keepsake`.
"""

from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import new_entity_id, recipient_pc
from aidm.dm.tools import GiveKeepsakeArgs, TakeItemArgs
from aidm.models.character import Keepsake
from aidm.models.state import Creature, GameState
from aidm.models.world_events import KeepsakeGained
from aidm.rules.dice import Rng
from aidm.rules.equipment import EquipRefused, take_events
from aidm.rules.quest_items import Spot, quest_item_named

MAX_KEEPSAKES = 20


def run_take_item(
    state: GameState, args: TakeItemArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    pc = recipient_pc(state, ctx)
    item = state.world.items.get(args.item_id)
    try:
        events = take_events(state, pc, args.item_id)
    except EquipRefused as refused:
        raise ToolRefused(f"{args.item_id!r}: {refused.detail}") from None
    name = item.name if item is not None else args.item_id
    return ToolResult(events=tuple(events), summary=f"{pc.name} picks up the {name}")


_SPOT_REFUSALS = {
    Spot.HIDDEN_HERE: "{name} is not found yet: a search here might turn it up",
    Spot.ELSEWHERE: "{name} is not here: it lies somewhere else",
    Spot.CARRIED: "{name} is already carried by {holder}",
    Spot.GIVEN: "{name} was already handed to {holder}",
}


def _quest_item(state: GameState, pc: Creature, name: str) -> ToolResult | None:
    spot = quest_item_named(state, name)
    if spot is None:
        return None
    if spot.spot is not Spot.HERE:
        detail = _SPOT_REFUSALS[spot.spot].format(name=spot.name, holder=spot.holder)
        raise ToolRefused(f"{name!r} is a quest item: {detail}")
    events = take_events(state, pc, spot.item_id)
    return ToolResult(events=tuple(events), summary=f"{pc.name} picks up the {spot.name}")


def run_give_keepsake(
    state: GameState, args: GiveKeepsakeArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    pc = recipient_pc(state, ctx)
    assert pc.pc is not None
    real = _quest_item(state, pc, args.name)
    if real is not None:
        return real
    held = pc.pc.keepsakes
    if len(held) >= MAX_KEEPSAKES:
        raise ToolRefused(f"{pc.name} already carries {MAX_KEEPSAKES} keepsakes")
    if any(k.name.casefold() == args.name.strip().casefold() for k in held):
        raise ToolRefused(f"{pc.name} already carries the {args.name}")
    taken = [k.id for c in state.creatures.values() if c.pc is not None for k in c.pc.keepsakes]
    keepsake = Keepsake(
        id=new_entity_id("keepsake", args.name, [*taken, *state.world.items]),
        name=args.name.strip(),
        description=args.description.strip(),
    )
    event = KeepsakeGained(creature_id=pc.id, keepsake=keepsake)
    return ToolResult(events=(event,), summary=f"{pc.name} now carries the {keepsake.name}")
