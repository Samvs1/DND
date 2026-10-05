"""Campaign persistence: `saves/<campaign_id>/` (SPEC 4 Persistence, DECISIONS M6.3).

Files per campaign:
- `initial.json`: the `GameState` the log replays from (written once, never rewritten);
- `events.jsonl`: append-only, one `LoggedEvent` per line, flushed and fsynced per append;
- `snapshot.json`: `{version, seq, saved_at, state}` the latest state (atomic temp + `os.replace`);
- `table.json`: `TableMeta` (seats with their tokens, id counter, TTS flag), atomic too.

`load` replays `events.jsonl` from `initial.json` and asserts the result equals the snapshot.
The log is the source of truth: a missing, corrupt or stale snapshot is replaced by the replay
(`recovered=True`, `notes` say why); a partial last line (crash mid-append) is dropped. Without a
usable `initial.json` the snapshot alone is used with an empty log (`recovered=True`).

Public API: `CampaignStore`, `LoadedCampaign`, `TableMeta`, `SeatRecord`, `SaveInfo`,
`CampaignLoadError`, `new_game_state`, `valid_campaign_id`.
"""

import contextlib
import json
import os
import random
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aidm.models.events import LoggedEvent
from aidm.models.state import GameState
from aidm.session.reducer import replay

SNAPSHOT_VERSION = 1
NL = chr(10)
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
INITIAL, EVENTS, SNAPSHOT, TABLE = "initial.json", "events.jsonl", "snapshot.json", "table.json"


class CampaignLoadError(Exception):
    """A save cannot be loaded at all (unknown id, no usable state)."""


def valid_campaign_id(campaign_id: str) -> bool:
    return _ID_RE.fullmatch(campaign_id) is not None


def new_game_state(seed: int | None = None) -> GameState:
    """A fresh empty game for a new table (the lobby phase)."""
    chosen = seed if seed is not None else random.SystemRandom().randrange(1, 2**31)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return GameState(campaign_id=f"c-{stamp}-{chosen % 10000:04d}", seed=chosen)


class SeatRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    token: str
    is_host: bool = False
    creature_id: str | None = None


class TableMeta(BaseModel):
    """Table-level data that is not `GameState` (seats, id counter, host flags)."""

    model_config = ConfigDict(extra="forbid")

    seats: list[SeatRecord] = Field(default_factory=list[SeatRecord])
    next_id: int = Field(default=1, ge=1)
    tts_enabled: bool = False


class SnapshotFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = SNAPSHOT_VERSION
    seq: int = Field(ge=0)
    saved_at: str
    state: GameState


@dataclass(frozen=True)
class SaveInfo:
    campaign_id: str
    seq: int
    saved_at: str


@dataclass
class LoadedCampaign:
    campaign_id: str
    initial: GameState
    state: GameState
    log: list[LoggedEvent]
    meta: TableMeta
    recovered: bool = False
    notes: list[str] = field(default_factory=list[str])


def _fsync_dir(path: Path) -> None:
    with contextlib.suppress(OSError):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` via a temp file in the same directory, then `os.replace`."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    _fsync_dir(path.parent)


def _state_json(state: GameState) -> object:
    return state.model_dump(mode="json")


class CampaignStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def folder(self, campaign_id: str) -> Path:
        if not valid_campaign_id(campaign_id):
            raise CampaignLoadError("That is not a valid campaign id.")
        return self.root / campaign_id

    def exists(self, campaign_id: str) -> bool:
        return valid_campaign_id(campaign_id) and (self.root / campaign_id / INITIAL).is_file()

    # --- writing -------------------------------------------------------------------------

    def save(
        self,
        campaign_id: str,
        *,
        initial: GameState,
        events: list[LoggedEvent],
        state: GameState,
        meta: TableMeta,
    ) -> None:
        """Append the new events (flush + fsync), then replace snapshot and table metadata."""
        folder = self.folder(campaign_id)
        folder.mkdir(parents=True, exist_ok=True)
        if not (folder / INITIAL).is_file():
            atomic_write(folder / INITIAL, initial.model_dump_json())
        if events:
            self.append(folder, events)
        snap = SnapshotFile(
            seq=state.event_count, saved_at=datetime.now(UTC).isoformat(), state=state
        )
        atomic_write(folder / SNAPSHOT, snap.model_dump_json())
        atomic_write(folder / TABLE, meta.model_dump_json())

    @staticmethod
    def append(folder: Path, events: list[LoggedEvent]) -> None:
        path = folder / EVENTS
        lines = "".join(e.model_dump_json() + NL for e in events)
        if path.is_file() and path.stat().st_size > 0:
            with path.open("rb") as tail:
                tail.seek(-1, os.SEEK_END)
                if tail.read(1) != b"\n":
                    lines = NL + lines
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(lines)
            handle.flush()
            os.fsync(handle.fileno())

    # --- reading -------------------------------------------------------------------------

    def list_campaigns(self) -> list[SaveInfo]:
        found: list[SaveInfo] = []
        if not self.root.is_dir():
            return found
        for folder in sorted(self.root.iterdir()):
            if not (folder.is_dir() and valid_campaign_id(folder.name)):
                continue
            if not (folder / INITIAL).is_file():
                continue
            found.append(self._info(folder))
        return sorted(found, key=lambda i: i.saved_at, reverse=True)

    @staticmethod
    def _info(folder: Path) -> SaveInfo:
        try:
            raw = json.loads((folder / SNAPSHOT).read_text(encoding="utf-8"))
            return SaveInfo(folder.name, int(raw["seq"]), str(raw["saved_at"]))
        except (OSError, ValueError, KeyError, TypeError):
            stamp = datetime.fromtimestamp((folder / INITIAL).stat().st_mtime, UTC)
            return SaveInfo(folder.name, 0, stamp.isoformat())

    def load(self, campaign_id: str) -> LoadedCampaign:
        folder = self.folder(campaign_id)
        if not folder.is_dir():
            raise CampaignLoadError("That saved campaign was not found.")
        notes: list[str] = []
        snapshot = _read_model(folder / SNAPSHOT, SnapshotFile, notes)
        initial = _read_model(folder / INITIAL, GameState, notes)
        meta = _read_model(folder / TABLE, TableMeta, notes) or TableMeta()
        if initial is None:
            if snapshot is None:
                raise CampaignLoadError("That saved campaign is damaged.")
            notes.append("no initial state: using the snapshot with an empty log")
            return LoadedCampaign(
                campaign_id, snapshot.state, snapshot.state, [], meta, True, notes
            )
        log = _read_log(folder / EVENTS, initial.event_count, notes)
        state = replay(initial, [entry.event for entry in log])
        recovered = bool(notes)
        if snapshot is not None and _state_json(snapshot.state) != _state_json(state):
            notes.append("snapshot differs from the replayed log: the log wins")
            recovered = True
        return LoadedCampaign(campaign_id, initial, state, log, meta, recovered, notes)


def _read_model[M: BaseModel](path: Path, model: type[M], notes: list[str]) -> M | None:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError):
        notes.append(f"{path.name} is missing or corrupt")
        return None


def _read_log(path: Path, first_seq: int, notes: list[str]) -> list[LoggedEvent]:
    """Parse events.jsonl; stop at the first bad line (a partial last line is normal)."""
    log: list[LoggedEvent] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return log
    except OSError:
        notes.append("events.jsonl is unreadable")
        return log
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = LoggedEvent.model_validate_json(line)
            ok = entry.seq == first_seq + len(log)
        except (ValidationError, ValueError):
            ok = False
        if not ok:
            notes.append(f"events.jsonl line {number} is damaged; the rest is dropped")
            atomic_write(path, "".join(e.model_dump_json() + NL for e in log))
            break
        log.append(entry)
    return log
