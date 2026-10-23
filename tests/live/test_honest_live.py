"""Live honest-storyteller probe (M29.5c, docs/playtests/M29_round1.md): skipped unless RUN_LIVE=1.

Replays six of round 1's worst moments against the real DeepSeek storyteller through THE one LLM
client, from the live saves (tests/fixtures/saves/m29-*): typed acts at a real table (precheck,
adjudicator, narrator, THE guard) and the narrator / epilogue alone for a fight beat and the end.
Assertions are on engine state and guard results, never on wording. Spend stays small: one turn
per case, no loops. Each case records one ASCII line through `live_say` (where the prose came
from, whether the guard made it regenerate, what it flagged).

Cases: "I drink my potion of giant strength" without one; "I buy the silk rope and pay Tann";
"I hand the scroll to Ranna"; a fight beat where the zombie is hit and survives (3 of 22 HP);
a light-crossbow attack; the epilogue of a state with a slain ally and a living turncoat.
M29.7b (docs/playtests/M29_round2.md): six round 2 fight beats that invented blows, hits, misses
and kills (R19), and four exploration turns: travel stopped short (R2), a torch already lit
(R17), a chime never lifted (R12), a hurt hero in a "whole" party (R28).
"""

import dataclasses
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from aidm.dm.epilogue import begin_epilogue, epilogue_checker
from aidm.dm.guard import prose_checker
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_settings import llm_settings_from_env
from aidm.dm.llm_types import LlmMode
from aidm.dm.narration_stream import NarrationStream
from aidm.dm.narrator import narrate, narrate_round_segment
from aidm.models.events import AnyEvent, GoldChanged, InventoryChanged
from aidm.models.protocol_client import SubmitAction
from aidm.models.quest_events import KeepsakeGiven
from aidm.models.state import GameState
from aidm.session.session_log import MemoryLog
from tests.ai.epilogue_fixtures import turned_and_dead
from tests.session.playtest_saves import replay_until, told_turn
from tests.session.table_fixtures import join, running

type Say = Callable[[str], None]


@pytest.fixture
async def client(tmp_path: Path, live_env: dict[str, str]) -> AsyncIterator[LlmClient]:
    settings = dataclasses.replace(
        llm_settings_from_env(live_env), log_path=tmp_path / "llm.jsonl", fake=False
    )
    made = make_llm_client(settings)
    if made.mode is not LlmMode.LIVE:
        pytest.fail("RUN_LIVE=1 needs DEEPSEEK_API_KEY in the environment or .env")
    await made.discover_models()
    yield made
    await made.aclose()


@dataclasses.dataclass
class Played:
    events: list[AnyEvent]
    before: GameState
    after: GameState
    diag: list[str]


async def play(llm: LlmClient, state: GameState, hero: str, text: str) -> Played:
    """One typed action by `hero` at a real table: its events and each narration's origin."""
    log = MemoryLog()
    async with running(llm, state.model_copy(deep=True), session_log=log) as (table, _):
        seat = await join(table, "Ann", hero)
        start = len(table.log)
        seat.send(SubmitAction(text=text))
        await table.settle()
        events = [entry.event for entry in table.log[start:]]
        after = table.state.model_copy(deep=True)
    diag = [
        f"{r.get('source')}{'+retry' if r.get('retried') else ''}"
        f"{' flags=' + ','.join(r.get('flags', [])) if r.get('flags') else ''}"
        for r in log.records("narration")
    ]
    return Played(events, state, after, diag)


def _record(say: Say, case: str, origin: list[str], extra: str = "") -> None:
    say(f"LIVE honest {case}: narration={origin or ['none']} {extra}".rstrip())


def _model_text(stream: NarrationStream) -> str:
    """The sentences the model wrote and the guard let through (not the engine's own lines)."""
    return " ".join(c.text for c in stream.chunks if not c.line)


def _stream_origin(stream: NarrationStream) -> list[str]:
    flags = [f"{v.kind.value}:{v.span}" for r in stream.reports for v in r.violations]
    retry = "+retry" if stream.retried else ""
    return [f"{stream.source.value}{retry}{' flags=' + ','.join(flags) if flags else ''}"]


def _pack(state: GameState, hero: str) -> tuple[int, dict[str, int], int]:
    pc = state.creatures[hero].pc
    assert pc is not None
    return pc.gold, {i.item: i.qty for i in pc.inventory}, len(pc.keepsakes)


async def test_live_claimed_potion_is_not_drunk(client: LlmClient, live_say: Say) -> None:
    played = await play(
        client, replay_until("p6", 35), "pc-p2", "I drink my potion of giant strength"
    )
    _record(live_say, "potion", played.diag)
    assert _pack(played.after, "pc-p2") == _pack(played.before, "pc-p2")
    assert not any(isinstance(e, InventoryChanged) for e in played.events)


async def test_live_purchase_only_through_the_shop(client: LlmClient, live_say: Say) -> None:
    played = await play(client, replay_until("p6", 57), "pc-p2", "I buy the silk rope and pay Tann")
    gold_before, items_before, _ = _pack(played.before, "pc-p2")
    gold_after, items_after, _ = _pack(played.after, "pc-p2")
    paid = any(isinstance(e, GoldChanged) for e in played.events)
    _record(live_say, "buy", played.diag, f"gold {gold_before}->{gold_after} paid_event={paid}")
    assert (gold_after != gold_before) == paid
    assert (items_after != items_before) == paid  # goods come only with a real sale


async def test_live_hand_over_is_real_or_nothing(client: LlmClient, live_say: Say) -> None:
    played = await play(client, replay_until("p3", 415), "pc-p6", "I hand the scroll to Ranna")
    given = [e for e in played.events if isinstance(e, KeepsakeGiven)]
    kept_before, kept_after = _pack(played.before, "pc-p6")[2], _pack(played.after, "pc-p6")[2]
    _record(live_say, "hand-over", played.diag, f"keepsakes {kept_before}->{kept_after}")
    assert kept_after == kept_before - len(given)


@pytest.mark.parametrize(("case", "seq"), [("survivor", 96), ("crossbow", 206)])
async def test_live_fight_beat_tells_the_truth(
    client: LlmClient, live_say: Say, case: str, seq: int
) -> None:
    turn = told_turn("p2", seq)
    stream = narrate_round_segment(turn.state, list(turn.events), client)
    text = await stream.collect()
    _record(live_say, case, _stream_origin(stream))
    assert text and prose_checker(turn.state, turn.events)(_model_text(stream)).ok


async def test_live_epilogue_follows_the_final_state(client: LlmClient, live_say: Say) -> None:
    state = turned_and_dead()
    stream = begin_epilogue(state, client)
    assert stream is not None
    text = await stream.collect()
    _record(live_say, "epilogue", _stream_origin(stream))
    assert text and epilogue_checker(state)(_model_text(stream)).ok


_ROUND_TWO_FIGHTS = [
    ("r19-claw", "r2-p4", 873),
    ("r19-oar", "r2-full", 1416),
    ("r19-shafts", "r2-full", 2061),
    ("r19-killer", "r2-full", 395),
    ("r19-skips", "r2-full", 87),
    ("r19-cut", "r2-p8", 158),
]


@pytest.mark.parametrize(("case", "run", "seq"), _ROUND_TWO_FIGHTS)
async def test_live_round_two_fight_beat(
    client: LlmClient, live_say: Say, case: str, run: str, seq: int
) -> None:
    """M29.7b R19: the round 2 fight beats whose prose invented blows, hits, misses and kills."""
    turn = told_turn(run, seq)
    stream = narrate_round_segment(turn.state, list(turn.events), client)
    text = await stream.collect()
    _record(live_say, case, _stream_origin(stream))
    assert text and prose_checker(turn.state, turn.events)(_model_text(stream)).ok


_ROUND_TWO_WORLD = [
    ("r2-short", "r2-p5", 684),
    ("r17-torch", "r2-p4", 214),
    ("r12-chime", "r2-p7", 871),
    ("r28-whole", "r2-p8", 683),
]


@pytest.mark.parametrize(("case", "run", "seq"), _ROUND_TWO_WORLD)
async def test_live_round_two_world_turn(
    client: LlmClient, live_say: Say, case: str, run: str, seq: int
) -> None:
    """M29.7b R2 R12 R17 R28: travel stopped short, a torch already lit, a chime never lifted,
    a hurt hero in a 'whole' party."""
    turn = told_turn(run, seq)
    stream = narrate(
        turn.state, list(turn.events), client, actor_id=turn.actor_id, player_text=turn.player_text
    )
    text = await stream.collect()
    _record(live_say, case, _stream_origin(stream))
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    assert text and check(_model_text(stream)).ok
