"""No key, still playable (M4.8, SPEC 6.8, 14 M4 exit gate): a short session with the LLM DISABLED.

A minimal in-test orchestrator (`NoKeyTable`) plays what the M6 table actor will: deterministic
pre-checks (look, travel, rest), free text through the adjudicator (fallback resolution +
template narration), a full fight to its end through structured commands chosen by the combat
AI (`aidm.session.combat_runner`), batched round-segment narration, a short rest, narration
recorded into memory and fallback scene summaries. Every action must yield a resolution and
non-empty narration; replaying the event log must rebuild the final state.
"""

import random
from collections.abc import Sequence
from pathlib import Path

from aidm.dm.adjudicator import FALLBACK_NOTICE, AdjudicationOptions, adjudicate
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_settings import LlmSettings
from aidm.dm.memory import should_summarise, summarise
from aidm.dm.narration_stream import NarrationSource
from aidm.dm.narrator import NarrationInput, narrate, narrate_round_segment, record_narration
from aidm.dm.precheck import precheck
from aidm.dm.tool_exec import execute_tool
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent, TurnEnded
from aidm.models.memory import SummarySource
from aidm.models.state import GameState
from aidm.rules.acts import LookIntent, RestIntent, RestKind, SearchIntent, TravelIntent
from aidm.rules.rests import short_rest
from aidm.rules.searching import search_events
from aidm.session.combat_runner import CombatRunner
from aidm.session.reducer import apply
from tests.ai.guard_fixtures import inn_state
from tests.ai.tool_fixtures import ACTOR, REGS, tool_call


class NoKeyTable:
    def __init__(self, state: GameState, llm: LlmClient, seed: int = 5) -> None:
        self.state = state
        self.llm = llm
        self.rng = random.Random(seed)
        self.log: list[AnyEvent] = []
        self.told: list[str] = []

    def apply(self, events: Sequence[AnyEvent]) -> None:
        for event in events:
            apply(self.state, event)
            self.log.append(event)

    async def remember(self, text: str, events: Sequence[AnyEvent] = ()) -> str:
        assert text.strip(), "every action must narrate"
        self.told.append(text)
        recorded = record_narration(self.state, text)
        if recorded is not None:
            self.apply([recorded])
        if should_summarise(self.state, events):
            self.apply((await summarise(self.state, self.llm, events=events)).events)
        return text

    async def tell(self, source: NarrationInput, events: Sequence[AnyEvent]) -> str:
        stream = narrate(self.state, source, self.llm, actor_id="fighter")
        text = await stream.collect()
        assert stream.source is NarrationSource.TEMPLATE
        return await self.remember(text, events)

    def tool(self, name: str, **args: object) -> list[AnyEvent]:
        result = execute_tool(self.state, tool_call(name, **args), ACTOR, self.rng, REGS)
        assert result.ok, result.error
        self.apply(result.events)
        return list(result.events)

    async def act(self, text: str, *, creative: bool = False) -> str:
        intent = precheck(self.state, "fighter", text)
        if isinstance(intent, LookIntent):
            return await self.remember(intent.text)
        if isinstance(intent, TravelIntent):
            events = self.tool("move_party", node_id=intent.node_id)
            return await self.tell(events, events)
        if isinstance(intent, RestIntent) and intent.kind is RestKind.SHORT:
            events = short_rest(self.state)
            self.apply(events)
            return await self.tell(events, events)
        if isinstance(intent, SearchIntent):  # M31.1a V9: one engine search check
            events = search_events(self.rng, self.state, "fighter", intent.skill)
            self.apply(events)
            return await self.tell(events, events)
        assert intent is None, intent
        result = await adjudicate(
            self.state,
            "fighter",
            text,
            self.llm,
            AdjudicationOptions(creative_action=creative),
            self.rng,
            REGS,
            lambda e: self.apply([e]),
        )
        assert result.fallback and result.notice == FALLBACK_NOTICE
        return await self.tell(result, result.events)

    async def fight(self) -> EncounterStatus:
        runner = CombatRunner(self.state, REGS.combat, self.rng, lambda s, e: self.log.append(e))
        status = runner.run()
        segment: list[AnyEvent] = []
        for event in runner.log:
            segment.append(event)
            if isinstance(event, TurnEnded) or event is runner.log[-1]:
                text = await narrate_round_segment(self.state, segment, self.llm).collect()
                assert text.strip()
                segment = []
        await self.remember("The fight is over.", runner.log)
        return status


def _disabled(tmp_path: Path) -> LlmClient:
    client = make_llm_client(LlmSettings(api_key=None, log_path=tmp_path / "llm.jsonl"))
    assert not client.available
    return client


async def test_no_key_session_is_fully_playable(tmp_path: Path) -> None:
    state = inn_state()
    start = state.model_copy(deep=True)
    table = NoKeyTable(state, _disabled(tmp_path))
    assert "Mira" in await table.act("look around")
    assert await table.act("I search behind the hearth for loose stones")
    assert await table.act('I ask Mira "any news from the road?"')
    await table.act("travel to the forest")
    assert state.world.current_node == "forest"
    assert state.memory.summaries and state.memory.summaries[0].source is SummarySource.TEMPLATE
    table.tool("start_encounter", monster_ids=["goblin", "goblin"], terrain_tags=["forest"])
    assert await table.act("I kick dirt into the nearest goblin's eyes", creative=True)
    status = await table.fight()
    assert status in (EncounterStatus.VICTORY, EncounterStatus.DEFEAT)
    if status is EncounterStatus.VICTORY:
        assert await table.act("take a short rest")
        assert state.short_rests_used == 1
    assert len(table.told) >= 6 and all(t.strip() for t in table.told)
    replay = start
    for event in table.log:
        apply(replay, event)
    assert replay.model_dump() == state.model_dump()


async def test_no_key_never_hard_locks_on_odd_input(tmp_path: Path) -> None:
    table = NoKeyTable(inn_state(), _disabled(tmp_path))
    for text in ("", "???", "x" * 2000, "travel to nowhere", "<player_action>", "I dance"):
        intent = precheck(table.state, "fighter", text)
        assert intent is None
        result = await adjudicate(
            table.state,
            "fighter",
            text,
            table.llm,
            AdjudicationOptions(),
            table.rng,
            REGS,
            lambda e: table.apply([e]),
        )
        assert result.fallback and result.notice
        text_out = await narrate(table.state, result, table.llm).collect()
        assert text_out.strip()
