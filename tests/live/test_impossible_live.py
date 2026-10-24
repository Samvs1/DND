"""Live impossible-action probe (M30.2, docs/next/GOAL_IMPOSSIBLE.md "Done means"): skipped unless
RUN_LIVE=1. Run only these: `pytest -q tests/live -k m30`.

Three typed actions at the docks beside a two-storey warehouse, each through the real adjudicate
path (`aidm.dm.adjudicator.adjudicate`, THE one context builder, THE one LLM client, DeepSeek):

- "jump straight up onto the roof in one leap" (fighter): `ActionImpossible`, no dice;
- "climb the sheer wall to the roof" (fighter, hard but possible): a check or another resolution,
  never impossible;
- "cast misty step to reach the roof" (wizard with Misty Step prepared): never impossible, and
  (M30.2b) cast by the engine on the real table, the 2nd-level slot spent; the model narrates.

Assertions are on engine events only. Spend stays small: one adjudication per case, no retries.
Each case records one ASCII line through `live_say`: the model's tool calls (name and full
arguments) and the calls and tokens it wrote to logs/llm.jsonl.
"""

import dataclasses
import json
import random
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from aidm.dm.adjudicator import AdjudicationOptions, AdjudicationResult, adjudicate
from aidm.dm.llm_backend import Completion, CompletionRequest, LlmBackend, StreamChunk
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_settings import llm_settings_from_env
from aidm.dm.llm_types import LlmMode
from aidm.dm.tool_context import ToolContext
from aidm.models.combat_events import SpellCast
from aidm.models.events import CheckResolved, DiceRolled, ResourceSet
from aidm.models.impossible import ActionImpossible
from aidm.models.protocol_client import SubmitAction
from aidm.models.state import GameState
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import REGS, apply_result, run_tool
from tests.session.table_fixtures import join, running
from tests.sim.sim_setup import build_party
from tests.unit.rules.item_fixtures import DOCKS, at

type Say = Callable[[str], None]
ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "logs" / "llm.jsonl"
LEAP = "I jump straight up from the quay onto the roof of the warehouse in one leap"
CLIMB = "I climb the sheer stone wall of the warehouse up to the roof"
BLINK = "I cast misty step to reach the roof of the warehouse"


class RecordingBackend:
    """Wraps the live backend and records every tool call the model returns, in full."""

    def __init__(self, inner: LlmBackend) -> None:
        self.inner = inner
        self.calls: list[str] = []

    async def complete(self, request: CompletionRequest) -> Completion:
        done = await self.inner.complete(request)
        self.calls += [f"{c.name}({c.arguments})" for c in done.tool_calls]
        return done

    def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        return self.inner.stream(request)

    async def list_models(self) -> list[str]:
        return await self.inner.list_models()

    async def aclose(self) -> None:
        await self.inner.aclose()


@pytest.fixture
async def client(live_env: dict[str, str]) -> AsyncIterator[LlmClient]:
    settings = dataclasses.replace(llm_settings_from_env(live_env), log_path=LOG, fake=False)
    made = make_llm_client(settings)
    if made.mode is not LlmMode.LIVE:
        pytest.fail("RUN_LIVE=1 needs DEEPSEEK_API_KEY in the environment or .env")
    made.backend = RecordingBackend(made.backend)
    await made.discover_models()
    yield made
    await made.aclose()


def _warehouse() -> GameState:
    state = at(DOCKS)
    build_party(state, 3)
    wizard = state.creatures["wizard"].pc
    assert wizard is not None
    wizard.spellbook.append("misty-step")
    wizard.prepared.append("misty-step")
    result = run_tool(
        state,
        "introduce_feature",
        ctx=ToolContext(actor_id="fighter"),
        kind="object",
        name="Warehouse",
        description="a two-storey stone warehouse with sheer walls and a flat roof",
    )
    apply_result(state, result)
    return state


def _log_lines() -> list[str]:
    return LOG.read_text(encoding="utf-8").splitlines() if LOG.exists() else []


def _spend(lines: list[str]) -> str:
    rows = [json.loads(line) for line in lines]
    prompt = sum(int(r.get("prompt_tokens") or 0) for r in rows)
    done = sum(int(r.get("completion_tokens") or 0) for r in rows)
    return f"llm_calls={len(rows)} prompt_tokens={prompt} completion_tokens={done}"


async def _probe(llm: LlmClient, say: Say, case: str, actor: str, text: str) -> AdjudicationResult:
    state = _warehouse()
    before = len(_log_lines())
    result = await adjudicate(
        state,
        actor,
        text,
        llm,
        AdjudicationOptions(),
        random.Random(5),
        REGS,
        lambda e: apply(state, e),
    )
    backend = llm.backend
    calls = backend.calls if isinstance(backend, RecordingBackend) else []
    kinds = sorted({e.type for e in result.events})
    say(f"LIVE m30 {case}: calls={calls or ['none']} events={kinds} fallback={result.fallback}")
    say(f"LIVE m30 {case}: {_spend(_log_lines()[before:])}")
    return result


async def test_live_m30_impossible_leap(client: LlmClient, live_say: Say) -> None:
    result = await _probe(client, live_say, "leap", "fighter", LEAP)
    assert [type(e) for e in result.events] == [ActionImpossible]
    assert not any(isinstance(e, CheckResolved | DiceRolled) for e in result.events)


async def test_live_m30_hard_climb_is_a_check(client: LlmClient, live_say: Say) -> None:
    result = await _probe(client, live_say, "climb", "fighter", CLIMB)
    assert not result.fallback and result.calls  # a check or another resolution
    assert not any(isinstance(e, ActionImpossible) for e in result.events)


async def test_live_m30_misty_step_is_possible(client: LlmClient, live_say: Say) -> None:
    """M30.2b: the typed cast goes through the engine on the real table before the model (the
    first probe got `no_mechanics`: a free spell); the live model only narrates the cast."""
    state = _warehouse()
    before = len(_log_lines())
    async with running(client, state) as (table, _):
        seat = await join(table, "Ann", "wizard")
        start = table.state.event_count
        seat.send(SubmitAction(text=BLINK))
        await table.settle()
        events = [e.event for e in table.log if e.seq >= start]
    kinds = sorted({e.type for e in events})
    live_say(f"LIVE m30 blink: events={kinds} {_spend(_log_lines()[before:])}")
    assert [e.spell_id for e in events if isinstance(e, SpellCast)] == ["misty-step"]
    assert any(isinstance(e, ResourceSet) and e.key == "spell-slot-2" for e in events)
    assert not any(isinstance(e, ActionImpossible) for e in events)
