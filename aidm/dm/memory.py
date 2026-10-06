"""DM memory: scene summaries and the fact ledger (SPEC 6.4 sections 4-5, 6.6).

Trigger policy (`should_summarise`): summarise after `SUMMARY_EVERY_TURNS` narrated turns, or
as soon as a scene ended with at least one unsummarised turn. A scene ends when the party moved
(`PartyMoved` in the events, or the run of unsummarised turns began in an earlier scene) or a
fight ended (`EncounterEnded` in the events). The session calls it after recording a turn's
narration (`aidm.dm.narrator.record_narration`) and, when True, applies `summarise(...).events`.

`summarise` makes ONE structured FAST call (`LlmClient.structured`, schema `SummaryDraft`) over
the SUMMARIZE context pack (manifest with ids, no NPC private data) plus the narrated turns to
cover. The engine then disposes: the summary and title must pass THE guard
(`aidm.dm.guard.prose_checker`, limited to `SUMMARY_GUARD_KINDS`: a past-tense recap legitimately
names people of an earlier scene and creatures that died), at most `MAX_SUMMARY_SENTENCES`
sentences are kept, entity ids must be known (`aidm.dm.tool_exec_ledger.known_entity_ids`),
a fact keeps only known ids and is dropped without any (or when its text fails the guard), at
most `MAX_SUMMARY_FACTS` facts.
Facts enter the ledger through the same constructor as the `record_fact` tool
(`aidm.dm.tool_exec_ledger.new_fact`) and are tagged `SUMMARY_TAG`. A failed call or a summary
the guard rejects falls back to `aidm.dm.memory_fallback.fallback_summary` (no invention).

Retrieval: the context builder ranks facts with `aidm.dm.context_sections.relevant_facts`
(top-k by entity-id overlap, ties by recency): the ONE retrieval function.

Public API: `SUMMARY_EVERY_TURNS`, `MAX_SUMMARY_SENTENCES`, `MAX_SUMMARY_FACTS`, `SUMMARY_TAG`,
`SUMMARY_GUARD_KINDS`, `SummaryFact`, `SummaryDraft`, `summary_checker(state, events)`,
`SummaryOutcome(summary, events, failure, dropped)`,
`scene_ended(state, events=())`, `should_summarise(state, events=())`,
`summary_messages(state, events, budget_tokens)`, `async summarise(state, llm, *, events,
budget_tokens) -> SummaryOutcome`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from aidm.dm.context import DEFAULT_BUDGET_TOKENS, build_context, to_messages
from aidm.dm.context_text import ContextPurpose
from aidm.dm.guard import prose_checker
from aidm.dm.guard_types import GuardReport, ProseCheck, ViolationKind
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmFailure, LlmRole
from aidm.dm.memory_fallback import (
    DraftFact,
    fallback_facts,
    fallback_summary,
    turns_to_summarise,
)
from aidm.dm.sentence_chunker import split_sentences
from aidm.dm.tool_exec_ledger import known_entity_ids, new_fact
from aidm.models.encounter_events import EncounterEnded
from aidm.models.events import AnyEvent
from aidm.models.memory import SceneSummary, SummarySource
from aidm.models.state import GameState
from aidm.models.world_events import FactRecorded, PartyMoved, SceneSummarised

SUMMARY_EVERY_TURNS = 12
MAX_SUMMARY_SENTENCES = 4
MAX_SUMMARY_FACTS = 5
SUMMARY_TAG = "summary"
SUMMARY_GUARD_KINDS = frozenset(
    {
        ViolationKind.UNKNOWN_NAME,
        ViolationKind.WRONG_IDENTITY,
        ViolationKind.ITEM_DESTROYED,
        ViolationKind.UNLISTED_FEATURE,
        ViolationKind.SECRET_LEAK,
    }
)
SUMMARY_RULES = (
    "Summarise ONLY the narrated turns listed above in 2 to 4 plain past-tense sentences."
    " Name only entities listed in the manifest; invent nothing. title: 3 to 6 words in"
    " sentence case (capitalise only the first word and names). entity_ids: ids shown in"
    " brackets in the manifest for every entity involved. facts: up to 5 durable things the"
    " party learned or changed (who wants what, where something is, what was promised), each"
    " with the bracketed ids it concerns and one or two short tags."
)


class SummaryFact(BaseModel):
    """One durable fact from the scene, tagged with the entity ids it concerns."""

    text: str = Field(min_length=1, max_length=300)
    entity_ids: list[str] = Field(default_factory=list[str])
    tags: list[str] = Field(default_factory=list[str])


class SummaryDraft(BaseModel):
    """Return the scene summary: a short title, 2 to 4 plain sentences, the ids of the entities
    involved and up to 5 durable facts tagged with entity ids."""

    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=900)
    entity_ids: list[str] = Field(default_factory=list[str])
    facts: list[SummaryFact] = Field(default_factory=list[SummaryFact])


@dataclass(frozen=True)
class SummaryOutcome:
    summary: SceneSummary
    events: tuple[AnyEvent, ...]
    failure: LlmFailure | None = None
    dropped: tuple[str, ...] = ()


def scene_ended(state: GameState, events: Sequence[AnyEvent] = ()) -> bool:
    memory = state.memory
    moved_on = memory.turns_since_summary > 0 and memory.since_scene != state.world.scene_index
    return moved_on or any(isinstance(e, PartyMoved | EncounterEnded) for e in events)


def should_summarise(state: GameState, events: Sequence[AnyEvent] = ()) -> bool:
    turns = state.memory.turns_since_summary
    return turns >= SUMMARY_EVERY_TURNS or (turns > 0 and scene_ended(state, events))


def summary_messages(
    state: GameState,
    events: Sequence[AnyEvent] = (),
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> list[dict[str, Any]]:
    pack = build_context(
        state, ContextPurpose.SUMMARIZE, events=events, budget_tokens=budget_tokens, narration_n=0
    )
    turns = turns_to_summarise(state) or ["(nothing was narrated; use the engine events)"]
    listed = "\n".join(f"- {t}" for t in turns)
    extra = f"## NARRATED TURNS TO SUMMARISE\n{listed}\n\n## RULES\n{SUMMARY_RULES}"
    return [*to_messages(pack), {"role": "user", "content": extra}]


def summary_checker(state: GameState, events: Sequence[AnyEvent] = ()) -> ProseCheck:
    base = prose_checker(state, events)

    def check(text: str) -> GuardReport:
        found = base(text).violations
        return GuardReport(tuple(v for v in found if v.kind in SUMMARY_GUARD_KINDS))

    return check


def _outcome(
    state: GameState,
    summary: SceneSummary,
    facts: Sequence[DraftFact],
    **extra: Any,
) -> SummaryOutcome:
    events: list[AnyEvent] = [SceneSummarised(summary=summary)]
    for offset, fact in enumerate(facts[:MAX_SUMMARY_FACTS]):
        built = new_fact(state, fact.text, fact.entity_ids, (*fact.tags, SUMMARY_TAG), offset)
        events.append(FactRecorded(fact=built))
    return SummaryOutcome(summary, tuple(events), **extra)


def _facts(
    draft: SummaryDraft, known: set[str], check: ProseCheck, dropped: list[str]
) -> list[DraftFact]:
    kept: list[DraftFact] = []
    for fact in draft.facts[:MAX_SUMMARY_FACTS]:
        ids = tuple(dict.fromkeys(i for i in fact.entity_ids if i in known))
        if not ids or not check(fact.text).ok:
            dropped.append(f"fact {fact.text[:40]!r}")
            continue
        kept.append(DraftFact(fact.text.strip(), ids, tuple(fact.tags)))
    return kept


def _from_draft(
    state: GameState, draft: SummaryDraft, events: Sequence[AnyEvent]
) -> SummaryOutcome | None:
    check = summary_checker(state, events)
    sentences = split_sentences(draft.summary)[:MAX_SUMMARY_SENTENCES]
    text = " ".join(sentences)
    if not text or not check(text).ok:
        return None
    memory = state.memory
    title = draft.title.strip() if check(draft.title).ok else ""
    known = known_entity_ids(state)
    dropped = [f"id {i}" for i in draft.entity_ids if i not in known]
    ids = [memory.since_node] if memory.since_node else []
    ids += [i for i in draft.entity_ids if i in known]
    summary = SceneSummary(
        scene_index=memory.since_scene,
        node_id=memory.since_node,
        text=text,
        title=title or fallback_summary(state).title,
        entity_ids=tuple(dict.fromkeys(ids)),
        turns=memory.turns_since_summary,
        source=SummarySource.MODEL,
    )
    facts = _facts(draft, known, check, dropped)
    return _outcome(state, summary, facts, dropped=tuple(dropped))


async def summarise(
    state: GameState,
    llm: LlmClient,
    *,
    events: Sequence[AnyEvent] = (),
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
) -> SummaryOutcome:
    messages = summary_messages(state, events, budget_tokens)
    draft = await llm.structured(messages, SummaryDraft, LlmRole.FAST)
    failure = draft if isinstance(draft, LlmFailure) else None
    if not isinstance(draft, LlmFailure):
        built = _from_draft(state, draft, events)
        if built is not None:
            return built
    facts = fallback_facts(state, events)
    dropped = () if failure is not None else ("summary rejected by the guard",)
    return _outcome(state, fallback_summary(state, events), facts, failure=failure, dropped=dropped)
