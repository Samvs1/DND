"""One save folder loaded for the contract checks, and the walk over its events (M43.1)."""

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Protocol

from aidm.models.events import AnyEvent, LoggedEvent
from aidm.models.state import GameState
from aidm.session.persistence import SnapshotFile
from aidm.session.reducer import apply
from scripts.audit.replay import log_events


class Finding(NamedTuple):
    rule: str
    idx: int
    reason: str


class Visitor(Protocol):
    """A rule checked in the one walk: `see` gets the state BEFORE the event is applied."""

    def see(self, seq: int, state: GameState, event: AnyEvent) -> list[Finding]: ...

    def end(self, state: GameState) -> list[Finding]: ...


@dataclass
class Save:
    name: str
    folder: Path
    initial: GameState | None
    events: list[LoggedEvent]

    @property
    def snapshot(self) -> GameState | None:
        path = self.folder / "snapshot.json"
        if not path.exists():
            return None
        return SnapshotFile.model_validate_json(path.read_text("utf-8")).state


def load_save(folder: Path) -> Save:
    path = folder / "initial.json"
    initial = GameState.model_validate_json(path.read_text("utf-8")) if path.exists() else None
    return Save(folder.name, folder, initial, list(log_events(folder)))


def walk(save: Save, visitors: list[Visitor]) -> tuple[GameState, list[Finding]]:
    """Replay the log once through the reducer; every visitor sees each event first."""
    assert save.initial is not None
    state = save.initial.model_copy(deep=True)
    found: list[Finding] = []
    for entry in save.events:
        for visitor in visitors:
            found += visitor.see(entry.seq, state, entry.event)
        apply(state, entry.event)
    for visitor in visitors:
        found += visitor.end(state)
    return state, found
