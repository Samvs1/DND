"""Memory over FakeLLM (M4.7, SPEC 6.6): trigger policy, summariser, fallback, fact retrieval."""

import re
from pathlib import Path

from aidm.dm.context import SectionKey, build_context
from aidm.dm.context_sections import relevant_facts
from aidm.dm.context_text import ContextPurpose
from aidm.dm.entities import entity_registry
from aidm.dm.fake_llm import fake_tool_call
from aidm.dm.guard import check_prose
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_settings import LlmSettings
from aidm.dm.llm_types import FailureReason
from aidm.dm.memory import (
    SUMMARY_EVERY_TURNS,
    SUMMARY_TAG,
    scene_ended,
    should_summarise,
    summarise,
    summary_messages,
)
from aidm.dm.memory_fallback import fallback_summary
from aidm.dm.narrator import record_narration
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterEnded
from aidm.models.events import AnyEvent
from aidm.models.memory import SummarySource
from aidm.models.state import GameState
from aidm.models.world import Fact, NpcSecret
from aidm.models.world_events import FactRecorded, PartyMoved, SceneSummarised, SecretRevealed
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.guard_fixtures import inn_state
from tests.ai.tool_fixtures import add_npc, party_state

TURNS = (
    "Aria leans on the oak bar while Mira polishes a mug.",
    "Mira tells you about the old well behind the inn. She frowns at the hearth.",
    "Hobb the guard nods at Brannoc and steps aside.",
)


def _narrate(state: GameState, *texts: str) -> GameState:
    for text in texts:
        event = record_narration(state, text)
        assert event is not None
        apply(state, event)
    return state


def _disabled() -> LlmClient:
    return make_llm_client(LlmSettings(api_key=None, log_path=None))


def _apply_all(state: GameState, events: tuple[AnyEvent, ...]) -> None:
    for event in events:
        apply(state, event)


def test_trigger_every_twelve_turns() -> None:
    state = party_state()
    assert not should_summarise(state)
    _narrate(state, *(f"Turn {n} passes quietly." for n in range(SUMMARY_EVERY_TURNS - 1)))
    assert state.memory.turns_since_summary == SUMMARY_EVERY_TURNS - 1
    assert not should_summarise(state)
    _narrate(state, "One more turn passes.")
    assert should_summarise(state)


def test_trigger_at_scene_end() -> None:
    state = _narrate(party_state(), "You look around the square.")
    assert not should_summarise(state) and not scene_ended(state)
    assert should_summarise(state, [EncounterEnded(status=EncounterStatus.VICTORY)])
    apply(state, PartyMoved(from_node="town", to_node="forest", scene_index=1))
    assert scene_ended(state) and should_summarise(state)
    assert state.memory.since_scene == 0 and state.memory.since_node == "town"


def test_scene_summarised_resets_the_counter() -> None:
    state = _narrate(inn_state(), *TURNS)
    summary = fallback_summary(state)
    apply(state, SceneSummarised(summary=summary))
    assert state.memory.summaries == [summary] and state.memory.turns_since_summary == 0
    assert not should_summarise(state)
    _narrate(state, "The fire crackles.")
    assert state.memory.turns_since_summary == 1


async def test_fallback_summary_has_no_invented_names() -> None:
    state = _narrate(inn_state(), *TURNS)
    outcome = await summarise(state, _disabled())
    assert outcome.failure is not None and outcome.failure.reason is FailureReason.DISABLED
    summary = outcome.summary
    assert summary.source is SummarySource.TEMPLATE and summary.node_id == "town"
    assert check_prose(summary.text, state).ok
    known = {w.casefold() for n in entity_registry(state).all_names for w in n.split()}
    for word in re.findall(r"\b[A-Z][a-z]+\b", summary.text):
        assert word.casefold() in known or word in {"She", "The"}, word
    for sentence in summary.text.split(". "):
        assert any(sentence.rstrip(".") in turn for turn in TURNS)
    assert {"town", "npc-mira", "npc-hobb", "fighter"} <= set(summary.entity_ids)


async def test_fallback_without_narration_uses_events_only() -> None:
    state = inn_state()
    mira = state.world.npcs["npc-mira"]
    mira.secrets.append(NpcSecret(id="s1", text="the well water is poisoned"))
    event = SecretRevealed(npc_id="npc-mira", secret_id="s1")
    apply(state, event)
    outcome = await summarise(state, _disabled(), events=[event])
    facts = [e.fact for e in outcome.events if isinstance(e, FactRecorded)]
    assert len(facts) == 1 and facts[0].entity_ids == ("npc-mira",)
    assert SUMMARY_TAG in facts[0].tags and "secret" in facts[0].tags
    assert "Mira" in outcome.summary.text


async def test_model_summary_is_validated(tmp_path: Path) -> None:
    state = _narrate(inn_state(), *TURNS)
    draft = {
        "title": "Talk at the Lantern Inn",
        "summary": "Aria spoke with Mira at the bar. Mira mentioned the old well. Hobb stood by.",
        "entity_ids": ["npc-mira", "npc-ghost", "fighter"],
        "facts": [
            {
                "text": "Mira knows about the old well.",
                "entity_ids": ["npc-mira"],
                "tags": ["well"],
            },
            {"text": "Lord Vexmoor owns the well.", "entity_ids": ["npc-mira"], "tags": []},
            {"text": "Something stirs.", "entity_ids": ["npc-ghost"], "tags": []},
        ],
    }
    client, fake = fake_client(tmp_path, [fake_tool_call("submit_result", draft)])
    outcome = await summarise(state, client)
    assert fake.requests[0].model == "deepseek-flash"
    assert outcome.summary.source is SummarySource.MODEL and outcome.failure is None
    assert outcome.summary.entity_ids == ("town", "npc-mira", "fighter")
    facts = [e.fact for e in outcome.events if isinstance(e, FactRecorded)]
    assert [f.text for f in facts] == ["Mira knows about the old well."]
    assert facts[0].tags == ("well", SUMMARY_TAG) and len(outcome.dropped) == 3
    _apply_all(state, outcome.events)
    assert state.world.facts[-1].id == "fact-1" and state.memory.turns_since_summary == 0
    assert state.memory.summaries[-1].title == "Talk at the Lantern Inn"


async def test_invented_summary_falls_back(tmp_path: Path) -> None:
    state = _narrate(inn_state(), *TURNS)
    draft = {"title": "Plot", "summary": "Sister Kelene whispered to Mira.", "entity_ids": []}
    client, _ = fake_client(tmp_path, [fake_tool_call("submit_result", draft)])
    outcome = await summarise(state, client)
    assert outcome.summary.source is SummarySource.TEMPLATE and "Kelene" not in outcome.summary.text
    assert outcome.dropped == ("summary rejected by the guard",)


async def test_live_finding_real_summary_shape_is_kept(tmp_path: Path) -> None:
    """Live M9.4: DeepSeek's summary opened a sentence with "Nearby," (the guard took it for a
    name and rejected the whole summary) and wrote Title Case titles (every word an "unknown
    name"). The prompt now asks for a sentence-case title; both shapes are kept."""
    state = _narrate(inn_state(), *TURNS)
    draft = {
        "title": "Quiet word at the Lantern Inn",
        "summary": "Inside the smoky common room of the Lantern Inn, Aria leaned on the long"
        " oak bar while Mira polished a mug. Nearby, Hobb gave Brannoc a nod.",
        "entity_ids": ["npc-mira", "npc-hobb"],
    }
    client, fake = fake_client(tmp_path, [fake_tool_call("submit_result", draft)])
    outcome = await summarise(state, client)
    assert outcome.summary.source is SummarySource.MODEL, outcome.dropped
    assert outcome.summary.title == "Quiet word at the Lantern Inn"
    assert "sentence case" in str(fake.requests[0].messages[-1]["content"])


def test_summary_prompt_shows_ids_and_turns_but_no_secrets() -> None:
    state = _narrate(inn_state(), *TURNS)
    state.world.npcs["npc-mira"].secrets.append(NpcSecret(id="s1", text="she hid the ledger"))
    text = str(summary_messages(state))
    assert "[npc-mira]" in text and TURNS[1] in text and "hid the ledger" not in text


def _facts() -> list[Fact]:
    return [
        Fact(id="fact-1", text="old", entity_ids=("npc-a",)),
        Fact(id="fact-2", text="both", entity_ids=("npc-a", "town")),
        Fact(id="fact-3", text="none", entity_ids=("npc-z",)),
        Fact(id="fact-4", text="recent a", entity_ids=("npc-a",)),
    ]


def test_fact_retrieval_is_deterministic() -> None:
    facts = _facts()
    focus = {"npc-a", "town"}
    first = relevant_facts(facts, focus, 3)
    assert [f.id for f in first] == ["fact-2", "fact-4", "fact-1"]
    assert relevant_facts(facts, sorted(focus, reverse=True), 3) == first
    assert [f.id for f in relevant_facts(facts, set(), 2)] == ["fact-4", "fact-3"]
    assert relevant_facts(facts, focus, 0) == []


def test_context_uses_the_retrieval() -> None:
    state = party_state()
    add_npc(state)
    for fact in _facts():
        apply(state, FactRecorded(fact=fact))
    pack = build_context(state, ContextPurpose.NARRATE, facts_k=2)
    section = pack.section(SectionKey.FACTS)
    assert section is not None and list(section.lines) == ["both", "recent a"]
