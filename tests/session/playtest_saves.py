"""The M29 round 1 playtest saves as fixtures (owner rule: real saves stay as fixtures).

tests/fixtures/saves/m29-<run>/ holds the run's `initial.json` and a gzipped prefix of its
`events.jsonl` (live DeepSeek runs, docs/playtests/M29_round1.md). `replay_until(run, seq)`
replays every event before `seq` through the one reducer, so a test starts exactly where the
playtester stood.
"""

import gzip
from functools import cache
from pathlib import Path

from aidm.models.events import LoggedEvent
from aidm.models.state import GameState
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
