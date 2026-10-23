"""The M29 round 1 playtest saves as fixtures (owner rule: real saves stay as fixtures).

tests/fixtures/saves/m29-<run>/ holds the run's `initial.json` and a gzipped prefix of its
`events.jsonl` (live DeepSeek runs, docs/playtests/M29_round1.md). `replay_until(run, seq)`
replays every event before `seq` through the one reducer, so a test starts exactly where the
playtester stood. `told_turn(run, seq)` rebuilds what the narration at `seq` was told about
(M29.5c: the state, the turn's events, the typed action and the prose the live model wrote).
"""

import gzip
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from aidm.models.events import AnyEvent, LoggedEvent
from aidm.models.state import GameState
from aidm.models.world_events import (
    ActionDeclared,
    FactRecorded,
    NarrationRecorded,
    SceneSummarised,
)
from aidm.session.persistence import replay_log

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "saves"


@cache
def _log(run: str) -> tuple[GameState, tuple[LoggedEvent, ...]]:
    folder = FIXTURES / f"m29-{run}"
    initial = GameState.model_validate_json((folder / "initial.json").read_text("utf-8"))
    with gzip.open(folder / "events.jsonl.gz", "rt", encoding="utf-8") as raw:
        log = tuple(LoggedEvent.model_validate_json(line) for line in raw if line.strip())
    return initial, log


def replay_until(run: str, seq: int) -> GameState:
    initial, log = _log(run)
    return replay_log(initial, [e for e in log if e.seq < seq])


def logged(run: str, seq: int) -> LoggedEvent:
    return next(e for e in _log(run)[1] if e.seq == seq)


def events_of(run: str) -> tuple[LoggedEvent, ...]:
    return _log(run)[1]


@dataclass(frozen=True)
class ToldTurn:
    """What the narration at `seq` was told about: the state it was told in (every event before
    it applied), the engine events since the turn's typed action, and that action."""

    state: GameState
    events: tuple[AnyEvent, ...]
    actor_id: str | None
    player_text: str | None
    prose: str


_NOT_TOLD = (SceneSummarised, FactRecorded)


def told_turn(run: str, seq: int) -> ToldTurn:
    narration = logged(run, seq).event
    assert isinstance(narration, NarrationRecorded)
    before = [e for e in _log(run)[1] if e.seq < seq]
    told: list[AnyEvent] = []
    actor = text = None
    for entry in reversed(before):
        event = entry.event
        if isinstance(event, NarrationRecorded):
            break
        if isinstance(event, ActionDeclared):
            actor, text = event.creature_id, event.text
            break
        if not isinstance(event, _NOT_TOLD):
            told.insert(0, event)
    return ToldTurn(replay_until(run, seq), tuple(told), actor, text, narration.text)
