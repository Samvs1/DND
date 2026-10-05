"""Deterministic scene summary without a model (SPEC 6.6, 6.8): no key, outage or bad output.

Built ONLY from what the engine already holds, so it cannot invent anything:
- the summary text reuses the first sentence of up to `MAX_FALLBACK_SENTENCES` recorded
  narration turns (each already passed THE guard), or the template lines of the given events
  when nothing was narrated, or one neutral line naming the registered place;
- `entity_ids` are the registered creatures, NPCs, visible features and quests whose names
  appear in that text, plus the place;
- facts come from engine events only: a revealed secret and a quest change.

Public API: `MAX_FALLBACK_SENTENCES`, `turns_to_summarise(state) -> list[str]`,
`ids_named_in(state, text) -> list[str]`, `fallback_facts(state, events) -> list[DraftFact]`,
`fallback_summary(state, events) -> SceneSummary`, `DraftFact(text, entity_ids, tags)`.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from aidm.dm.narration_templates import template_line
from aidm.dm.sentence_chunker import split_sentences
from aidm.models.events import AnyEvent
from aidm.models.memory import MAX_NARRATION_LOG, SceneSummary, SummarySource
from aidm.models.state import GameState
from aidm.models.world_events import QuestUpdated, SecretRevealed
from aidm.rules.scene import node_display_name

MAX_FALLBACK_SENTENCES = 4


@dataclass(frozen=True)
class DraftFact:
    text: str
    entity_ids: tuple[str, ...]
    tags: tuple[str, ...]


def turns_to_summarise(state: GameState) -> list[str]:
    memory = state.memory
    count = min(memory.turns_since_summary, MAX_NARRATION_LOG)
    return list(memory.narration[-count:]) if count > 0 else []


def _named(state: GameState) -> dict[str, str]:
    world = state.world
    names = {cid: c.name for cid, c in state.creatures.items()}
    names.update({nid: n.name for nid, n in world.npcs.items()})
    names.update({fid: f.name for fid, f in world.features.items() if not f.hidden or f.discovered})
    names.update({qid: q.title for qid, q in world.quests.items()})
    return names


def ids_named_in(state: GameState, text: str) -> list[str]:
    found: list[str] = []
    for ident, name in sorted(_named(state).items()):
        if name and re.search(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", text, re.I):
            found.append(ident)
    return found


def _picked(turns: Sequence[str]) -> list[str]:
    firsts = [s[0] for s in (split_sentences(t) for t in turns) if s]
    if len(firsts) > MAX_FALLBACK_SENTENCES:
        step = (len(firsts) - 1) / (MAX_FALLBACK_SENTENCES - 1)
        firsts = [firsts[round(i * step)] for i in range(MAX_FALLBACK_SENTENCES)]
    return list(dict.fromkeys(firsts))


def _event_lines(state: GameState, events: Sequence[AnyEvent]) -> list[str]:
    lines = [line for e in events if (line := template_line(state, e))]
    return list(dict.fromkeys(lines))[:MAX_FALLBACK_SENTENCES]


def fallback_facts(state: GameState, events: Sequence[AnyEvent]) -> list[DraftFact]:
    facts: list[DraftFact] = []
    for event in events:
        if isinstance(event, SecretRevealed) and event.npc_id in state.world.npcs:
            npc = state.world.npcs[event.npc_id]
            secret = next((s for s in npc.secrets if s.id == event.secret_id), None)
            if secret is not None:
                text = f"{npc.name} revealed: {secret.text}"
                facts.append(DraftFact(text, (npc.id,), ("secret",)))
        elif isinstance(event, QuestUpdated):
            quest = event.quest
            ids = tuple(i for i in (quest.id, quest.giver_npc_id) if i)
            text = f"Quest {quest.title} is {quest.state.value}."
            facts.append(DraftFact(text, ids, ("quest",)))
    return facts


def fallback_summary(state: GameState, events: Sequence[AnyEvent] = ()) -> SceneSummary:
    memory = state.memory
    place = node_display_name(state, memory.since_node) if memory.since_node else "the road"
    sentences = _picked(turns_to_summarise(state)) or _event_lines(state, events)
    if not sentences:
        sentences = [f"The party spent a quiet while at {place}."]
    text = " ".join(sentences)
    node_ids = [memory.since_node] if memory.since_node else []
    return SceneSummary(
        scene_index=memory.since_scene,
        node_id=memory.since_node,
        text=text,
        title=f"At {place}",
        entity_ids=tuple(dict.fromkeys([*node_ids, *ids_named_in(state, text)])),
        turns=memory.turns_since_summary,
        source=SummarySource.TEMPLATE,
    )
