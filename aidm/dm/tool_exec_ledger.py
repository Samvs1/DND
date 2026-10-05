"""Executors for `update_quest` and `record_fact` (SPEC 6.3, 6.6): state, not prose.

Quests: a new quest needs a title; completed and failed are final. Completing a quest given by
an NPC is a deed (`aidm.rules.social.deed_attitude_events`, moderate tier) - the only route past
the ally bar. Facts: every entity id must name something known (creature, NPC, feature, quest
or world node), so the ledger cannot invent entities.

Public API: `run_update_quest`, `run_record_fact` -> `ToolResult`; `known_entity_ids(state)`.
"""

from aidm.dm.tool_context import ToolContext, ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tool_exec_common import require_npc
from aidm.dm.tools import RecordFactArgs, UpdateQuestArgs
from aidm.models.dm_tiers import XpTier
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world import Fact, Quest, QuestState
from aidm.models.world_events import FactRecorded, QuestUpdated
from aidm.rules.dice import Rng
from aidm.rules.dm_tiers import deed_points
from aidm.rules.social import deed_attitude_events

QUEST_DEED_TIER = XpTier.MODERATE
FINAL_QUEST_STATES = frozenset({QuestState.COMPLETED, QuestState.FAILED})
MAX_TAG_CHARS = 24


def _quest(state: GameState, args: UpdateQuestArgs) -> Quest:
    old = state.world.quests.get(args.quest_id)
    if old is None:
        if not args.title:
            raise ToolRefused(f"unknown quest {args.quest_id!r}; a new quest needs a title")
        giver = require_npc(state, args.giver_npc).id if args.giver_npc else None
        return Quest(id=args.quest_id, title=args.title, state=args.state, giver_npc_id=giver)
    if old.state in FINAL_QUEST_STATES:
        raise ToolRefused(f"quest {old.id!r} is already {old.state.value}")
    return old.model_copy(update={"state": args.state})


def run_update_quest(
    state: GameState, args: UpdateQuestArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    quest = _quest(state, args)
    if state.world.quests.get(quest.id) == quest:
        return ToolResult(summary=f"quest {quest.id} unchanged")
    events: list[AnyEvent] = [QuestUpdated(quest=quest)]
    if quest.state is QuestState.COMPLETED and quest.giver_npc_id in state.world.npcs:
        giver = state.world.npcs[quest.giver_npc_id]
        points = deed_points(regs.tiers, QUEST_DEED_TIER)
        events.extend(deed_attitude_events(giver, points, f"completed quest {quest.id}"))
    return ToolResult(events=tuple(events), summary=f"quest {quest.title}: {quest.state.value}")


def known_entity_ids(state: GameState) -> set[str]:
    world = state.world
    known = set(state.creatures) | set(world.npcs) | set(world.features) | set(world.quests)
    known |= set(world.neighbours) | {n for ns in world.neighbours.values() for n in ns}
    if world.current_node is not None:
        known.add(world.current_node)
    return known


def run_record_fact(
    state: GameState, args: RecordFactArgs, ctx: ToolContext, rng: Rng, regs: ToolRegistries
) -> ToolResult:
    if not args.text.strip():
        raise ToolRefused("a fact needs text")
    unknown = [e for e in args.entity_ids if e not in known_entity_ids(state)]
    if unknown:
        raise ToolRefused(f"unknown entity ids: {', '.join(unknown)}")
    tags = tuple(dict.fromkeys(t.strip().lower()[:MAX_TAG_CHARS] for t in args.tags if t.strip()))
    fact = Fact(
        id=f"fact-{len(state.world.facts) + 1}",
        text=args.text.strip(),
        entity_ids=tuple(dict.fromkeys(args.entity_ids)),
        tags=tags,
    )
    return ToolResult(events=(FactRecorded(fact=fact),), summary=f"fact {fact.id} recorded")
