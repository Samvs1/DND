"""Executors of the item tools (M19.3, owner playtest 2026-10-10: "I pick up the pouch" was only
narrated; nothing could pick up a world item, and story finds such as a note were never carried).

`take_item` moves a visible item lying at the current place to the acting hero through
`rules.equipment.take_events` (a catalogue item into the inventory, anything else as a
keepsake). `give_keepsake` hands the acting hero a found story object: a `Keepsake` with no
value, at most `MAX_KEEPSAKES` per hero.

Public API: `MAX_KEEPSAKES`, `run_take_item`, `run_give_keepsake`.
"""

from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import new_entity_id, recipient_pc
from aidm.dm.tools import GiveKeepsakeArgs, TakeItemArgs
from aidm.models.character import Keepsake
from aidm.models.state import GameState
from aidm.models.world_events import KeepsakeGained
from aidm.rules.dice import Rng
from aidm.rules.equipment import EquipRefused, take_events

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


def run_give_keepsake(
    state: GameState, args: GiveKeepsakeArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    pc = recipient_pc(state, ctx)
    assert pc.pc is not None
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
