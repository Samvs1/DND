"""The session diagnostics log (M15.3): one JSON line per connection or turn event.

`SessionLog` is the sink the table writes to (`TableConfig.session_log`); the base class drops
everything. `MemoryLog` keeps the records (tests); `FileLog` appends a line per event to
`logs/session.jsonl` and rotates it to `session.1.jsonl` (one kept) past `cap_bytes`.
Records carry `ts`, `event`, `campaign_id` and the event fields; never a token or a key.
Logging never raises into game code: any failure drops the line.

Public API: `SessionLog`, `MemoryLog`, `FileLog`, `DEFAULT_CAP`.
"""

import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_CAP = 5 * 1024 * 1024


class SessionLog:
    def emit(self, event: str, campaign_id: str, **fields: Any) -> None:
        """Record one event; a failing sink is swallowed."""
        try:
            record = {"ts": time.time(), "event": event, "campaign_id": campaign_id, **fields}
            self.write(json.dumps(record, default=str, ensure_ascii=True))
        except Exception:
            return

    def write(self, line: str) -> None:
        return


class MemoryLog(SessionLog):
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, line: str) -> None:
        self.lines.append(line)

    def records(self, event: str | None = None) -> list[dict[str, Any]]:
        rows = [json.loads(line) for line in self.lines]
        return [r for r in rows if event is None or r["event"] == event]


class FileLog(SessionLog):
    def __init__(self, path: Path, cap_bytes: int = DEFAULT_CAP) -> None:
        self.path = path
        self.cap_bytes = cap_bytes

    def write(self, line: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size >= self.cap_bytes:
            os.replace(self.path, self.path.with_name(f"{self.path.stem}.1{self.path.suffix}"))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
