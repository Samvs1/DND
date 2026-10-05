"""Append-only call log `logs/llm.jsonl` (SPEC 4 DeepSeek).

One JSON line per provider attempt: timestamp, call kind, role, model, latency, token counts,
validation outcome, attempt number and, when the caller passes player text, a short SHA-256
hash of it. Never keys, never message content, never raw player text.

Public API:
- `hash_player_text(text) -> str`: 16 hex chars of SHA-256 (correlates turns without content).
- `LlmCallRecord`: the fields of one line.
- `LlmCallLog(path)`: `write(record)` appends a line (I/O errors are reported once through the
  `logging` module, never raised: logging must not break a turn). `path=None` disables writing.
"""

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

_LOG = logging.getLogger(__name__)


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
    ts: float = field(default_factory=time.time)


class LlmCallLog:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._warned = False

    def write(self, record: LlmCallRecord) -> None:
        if self.path is None:
            return
        line = json.dumps(asdict(record), sort_keys=True)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            if not self._warned:
                _LOG.warning("llm log not writable: %s", type(exc).__name__)
                self._warned = True
