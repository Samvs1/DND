"""Executor for `record_fact` (SPEC 6.3, 6.6): state, not prose. (`update_quest` moved to
`aidm.dm.tool_exec_quests` in M23.5.)

Facts: every entity id must name something known (creature, NPC, feature, quest or world node),
so the ledger cannot invent entities.

Public API: `run_record_fact` -> `ToolResult`; `known_entity_ids(state)`;
`new_fact(state, text, entity_ids, tags, offset=0) -> Fact` (the ONE way a ledger entry is built,
shared with the M4.7 summariser; `offset` numbers several facts recorded together).
"""

from collections.abc import Sequence

from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tools import RecordFactArgs
from aidm.models.state import GameState
from aidm.models.world import Fact
from aidm.models.world_events import FactRecorded
from aidm.rules.dice import Rng

MAX_TAG_CHARS = 24


def known_entity_ids(state: GameState) -> set[str]:
    world = state.world
    known = set(state.creatures) | set(world.npcs) | set(world.features) | set(world.quests)
    known |= set(world.neighbours) | {n for ns in world.neighbours.values() for n in ns}
    if world.current_node is not None:
        known.add(world.current_node)
    return known


def new_fact(
    state: GameState,
    text: str,
    entity_ids: Sequence[str],
    tags: Sequence[str],
    offset: int = 0,
) -> Fact:
    return Fact(
        id=f"fact-{len(state.world.facts) + 1 + offset}",
        text=text.strip(),
        entity_ids=tuple(dict.fromkeys(entity_ids)),
        tags=tuple(dict.fromkeys(t.strip().lower()[:MAX_TAG_CHARS] for t in tags if t.strip())),
    )


def run_record_fact(
    state: GameState, args: RecordFactArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    if not args.text.strip():
        raise ToolRefused("a fact needs text")
    unknown = [e for e in args.entity_ids if e not in known_entity_ids(state)]
    if unknown:
        raise ToolRefused(f"unknown entity ids: {', '.join(unknown)}")
    fact = new_fact(state, args.text, args.entity_ids, args.tags)
    return ToolResult(events=(FactRecorded(fact=fact),), summary=f"fact {fact.id} recorded")
