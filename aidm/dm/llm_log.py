"""Append-only call log `logs/llm.jsonl` (SPEC 4 DeepSeek).

One JSON line per provider attempt: timestamp, call kind, role, model, latency, token counts,
validation outcome, attempt number and, when the caller passes player text, a short SHA-256
hash of it. Never keys, never message content, never raw player text. A rejected attempt
(outcome invalid or truncated) also carries `errors`: the first validator messages (schema
messages, never input values), so the log shows why a call was retried (M16.1).

Public API:
- `hash_player_text(text) -> str`: 16 hex chars of SHA-256 (correlates turns without content).
- `LlmCallRecord`: the fields of one line (`errors` is left out of the line when empty).
- `short_errors(errors) -> tuple[str, ...]`: the first MAX_LOG_ERRORS, each without any
  `input_value=` fragment and cut to MAX_ERROR_CHARS.
- `LlmCallLog(path)`: `write(record)` appends a line (I/O errors are reported once through the
  `logging` module, never raised: logging must not break a turn). `path=None` disables writing.
"""

import hashlib
import json
import logging
import re
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

_LOG = logging.getLogger(__name__)
MAX_LOG_ERRORS = 5
MAX_ERROR_CHARS = 200
_INPUT_VALUE = re.compile(r"[\s,\[]*input_value=.*$", re.DOTALL)


def short_errors(errors: Sequence[str]) -> tuple[str, ...]:
    return tuple(_INPUT_VALUE.sub("", e)[:MAX_ERROR_CHARS] for e in errors[:MAX_LOG_ERRORS])


def hash_player_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class LlmCallRecord:
    kind: str
    role: str
    model: str
    latency_ms: int
    outcome: str
    attempt: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    player_text_hash: str | None = None
    errors: tuple[str, ...] = ()
    ts: float = field(default_factory=time.time)


class LlmCallLog:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._warned = False

    def write(self, record: LlmCallRecord) -> None:
        if self.path is None:
            return
        row = asdict(record)
        if not record.errors:
            del row["errors"]
        line = json.dumps(row, sort_keys=True)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            if not self._warned:
                _LOG.warning("llm log not writable: %s", type(exc).__name__)
                self._warned = True
