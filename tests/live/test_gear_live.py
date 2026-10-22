"""Live gear probe (M27.10, docs/next/GOAL_ITEMS.md "Done means"): skipped unless RUN_LIVE=1.

Typed actions at a real table (`aidm.session.table.Table`) with DeepSeek through THE one LLM
client: the deterministic precheck, the adjudicator, the executors, the narrator and THE guard.
Every assertion is on engine events, never on prose wording. Spend stays small: one table turn
per case (five cases), no retries or loops. Each case records one ASCII line through `live_say`:
the tool calls the model made (name and arguments, cut short) and the guard's flags on the
narration (`MemoryLog` "narration" records).

Cases:
- "I light my torch" in a dark cave: `LightLit` by the engine, the torch is used up, and a
  search there no longer has the *Darkness* disadvantage.
- "I use the rope to force open the lock": no check with advantage; the lock opens only with a
  `FeatureUnlocked` event (else it holds).
- "I read the scroll of sleep" in a fight: the spell engine casts Sleep, the scroll is gone.
- "I throw my bottle of water at the fire elemental" with a waterskin: thrown through the item
  rules, the waterskin is gone, a hit applies Water Susceptibility; WITHOUT a waterskin nothing
  is thrown, nothing is spent, nothing is hurt.
"""

import dataclasses
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest

from aidm.data.srd import srd
from aidm.dm.llm_backend import Completion, CompletionRequest, LlmBackend, StreamChunk
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_settings import llm_settings_from_env
from aidm.dm.llm_types import LlmMode
from aidm.dm.tool_context import ToolContext
from aidm.models.abilities import Skill
from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.dice import AdvState
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent, CheckResolved, DiceRolled, InventoryChanged
from aidm.models.item_events import FeatureUnlocked, ItemUsed, LightLit
from aidm.models.protocol_client import SubmitAction
from aidm.models.state import GameState
from aidm.models.world_events import FeatureIntroduced
from aidm.rules.light import sight_darkness
from aidm.rules.monster_stats import creature_from_monster
from aidm.session import combat_flow
from aidm.session.session_log import MemoryLog
from tests.ai.tool_fixtures import apply_result, run_tool
from tests.session.table_fixtures import join, running
from tests.unit.rules.combat_fixtures import monster
from tests.unit.rules.item_fixtures import CAVE, DOCKS, at, gear_fight, hero, qty

type Say = Callable[[str], None]
ROPE = "rope-hempen-50-feet"
WATER = "Water Susceptibility"
MAX_ARGS = 160


class RecordingBackend:
    """Wraps the live backend and records the tool calls the model returns (names + args)."""

    def __init__(self, inner: LlmBackend) -> None:
        self.inner = inner
        self.calls: list[str] = []

    async def complete(self, request: CompletionRequest) -> Completion:
        done = await self.inner.complete(request)
        self.calls += [f"{c.name}({c.arguments[:MAX_ARGS]})" for c in done.tool_calls]
        return done

    def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        return self.inner.stream(request)

    async def list_models(self) -> list[str]:
        return await self.inner.list_models()

    async def aclose(self) -> None:
        await self.inner.aclose()


@pytest.fixture
async def client(tmp_path: Path, live_env: dict[str, str]) -> AsyncIterator[LlmClient]:
    settings = dataclasses.replace(
        llm_settings_from_env(live_env), log_path=tmp_path / "llm.jsonl", fake=False
    )
    made = make_llm_client(settings)
    if made.mode is not LlmMode.LIVE:
        pytest.fail("RUN_LIVE=1 needs DEEPSEEK_API_KEY in the environment or .env")
    made.backend = RecordingBackend(made.backend)
    await made.discover_models()
    yield made
    await made.aclose()


@dataclasses.dataclass
class Turn:
    events: list[AnyEvent]
    state: GameState
    calls: list[str]
    flags: list[str]


async def play(llm: LlmClient, state: GameState, text: str) -> Turn:
    """One typed action by "hero" at a real table; the events it logged and what the AI did."""
    log = MemoryLog()
    backend = llm.backend
    seen = len(backend.calls) if isinstance(backend, RecordingBackend) else 0
    async with running(llm, state, session_log=log) as (table, _):
        seat = await join(table, "Ann", "hero")
        if table.combat_active():  # a prepared fight: the table enters it ("hero" acts first)

            async def enter() -> None:
                await combat_flow.after_resolution(table, [])

            table.schedule(enter)
            await table.settle()
        seat.send(SubmitAction(text=text))
        await table.settle()
        events = [entry.event for entry in table.log]
        final = table.state.model_copy(deep=True)
    calls = backend.calls[seen:] if isinstance(backend, RecordingBackend) else []
    flags = [str(f) for r in log.records("narration") for f in r.get("flags", [])]
    flags += [f"failure:{r['failure']}" for r in log.records("narration") if r.get("failure")]
    return Turn(events, final, calls, flags)


def _say(say: Say, case: str, turn: Turn, extra: str = "") -> None:
    kinds = sorted({e.type for e in turn.events})
    say(f"LIVE gear {case}: calls={turn.calls or ['none']} guard={turn.flags or ['clean']} {extra}")
    say(f"LIVE gear {case}: events={kinds}")


def _of[T](turn: Turn, kind: type[T]) -> list[T]:
    return [e for e in turn.events if isinstance(e, kind)]


def locked_chest(*gear: str) -> tuple[GameState, str]:
    state = at(DOCKS, hero(gear=list(gear)))
    args: dict[str, Any] = {"kind": "container", "name": "Iron chest", "lock_tier": "medium"}
    result = run_tool(state, "introduce_feature", ctx=ToolContext(actor_id="hero"), **args)
    apply_result(state, result)
    (event,) = result.events
    assert isinstance(event, FeatureIntroduced)
    return state, event.feature.id


def elemental_fight(*gear: str) -> GameState:
    elemental = creature_from_monster(srd().monsters.get("fire-elemental"), "fe")
    me = hero(gear=list(gear))
    me.max_hp = me.hp = 60  # the probe is about the throw, not about surviving the elemental
    return gear_fight(DOCKS, me, (elemental, Side.HOSTILE, "b"))


async def test_live_light_my_torch(client: LlmClient, live_say: Say) -> None:
    state = at(CAVE, hero(gear=["torch"]))
    assert sight_darkness(state, Skill.PERCEPTION)  # dark before
    turn = await play(client, state, "I light my torch")
    lit = _of(turn, LightLit)
    _say(live_say, "light", turn, f"lit={[(e.creature_id, e.item) for e in lit]}")
    assert [(e.creature_id, e.item) for e in lit] == [("hero", "torch")]
    assert qty(turn.state, "hero", "torch") == 0  # a torch is used up when lit
    assert sight_darkness(turn.state, Skill.PERCEPTION) == ()  # the next search rolls straight


async def test_live_rope_cannot_force_the_lock(client: LlmClient, live_say: Say) -> None:
    state, chest = locked_chest(ROPE)
    turn = await play(client, state, "I use the rope to force open the lock")
    checks = _of(turn, CheckResolved)
    opened = _of(turn, FeatureUnlocked)
    advs = [c.result.roll.adv.value for c in checks]
    _say(live_say, "rope", turn, f"checks={advs} unlocked={[e.method for e in opened]}")
    assert all(c.result.roll.adv is not AdvState.ADVANTAGE for c in checks)  # no rope advantage
    assert (turn.state.world.features[chest].lock is None) == bool(opened)
    assert not any(isinstance(e, ItemUsed) and e.item == ROPE for e in turn.events)


async def test_live_read_the_scroll_of_sleep(client: LlmClient, live_say: Say) -> None:
    state = gear_fight(
        CAVE, hero(gear=["scroll-of-sleep"]), (monster("gob", hp=5), Side.HOSTILE, "b")
    )
    turn = await play(client, state, "I read the scroll of sleep")
    casts = [(e.caster_id, e.spell_id) for e in _of(turn, SpellCast)]
    _say(live_say, "scroll", turn, f"casts={casts}")
    assert casts == [("hero", "sleep")]
    assert [e.item for e in _of(turn, ItemUsed)] == ["scroll-of-sleep"]
    assert qty(turn.state, "hero", "scroll-of-sleep") == 0


async def test_live_throw_water_at_the_fire_elemental(client: LlmClient, live_say: Say) -> None:
    text = "I throw my bottle of water at the fire elemental"
    turn = await play(client, elemental_fight("waterskin"), text)
    throws = [a for a in _of(turn, AttackRolled) if a.attacker_id == "hero"]
    weak = [d for d in _of(turn, DiceRolled) if d.label == WATER]
    used = [(e.item, e.use_id) for e in _of(turn, ItemUsed)]
    _say(live_say, "water", turn, f"used={used} hit={[a.hit for a in throws]} weak={len(weak)}")
    assert [item for item, _ in used] == ["waterskin"]  # thrown through the item rules
    assert qty(turn.state, "hero", "waterskin") == 0  # gone, hit or miss
    assert len(throws) == 1
    assert bool(weak) == throws[0].hit  # a hit splashes the water weakness (SRD 5.1)


async def test_live_throw_water_without_a_waterskin(client: LlmClient, live_say: Say) -> None:
    text = "I throw my bottle of water at the fire elemental"
    state = elemental_fight()
    hp = state.creatures["fe"].hp
    turn = await play(client, state, text)
    _say(live_say, "no-water", turn, f"fe_hp={hp}->{turn.state.creatures['fe'].hp}")
    assert not _of(turn, ItemUsed)  # refused: nothing is thrown
    assert not [e for e in _of(turn, InventoryChanged) if e.creature_id == "hero"]
    assert not [d for d in _of(turn, DiceRolled) if d.label == WATER]
    assert turn.state.creatures["fe"].hp == hp  # told as an attempt: nothing hurts it
