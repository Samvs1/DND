"""Shared half of the interpreter measurement scripts: the committed fixture runs, one walk over a
run that yields the state just before each typed line, and the menu built on that state.

`walk(run)` applies the run's events once through the reducer and yields a `Line` at each
`action_declared` event. The `state` of a `Line` is the live object and is only valid until the
generator advances (callers must not mutate it, and finish with it before the next `next()`).
"""

import gzip
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from aidm.data.combat_data import CombatRegistries, combat_registries
from aidm.data.item_catalogue import item_catalogue
from aidm.data.shop_defs import shop_table
from aidm.models.action_menu import ActionMenu
from aidm.models.events import AnyEvent, LoggedEvent
from aidm.models.state import GameState
from aidm.models.world_events import ActionDeclared
from aidm.rules.action_menu import build_menu
from aidm.rules.menu_trade import TradeData
from aidm.session.reducer import apply

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "saves"
RECENT = 60  # the same tail the table hands the chooser (session.menu_pick.RECENT)


@dataclass
class Line:
    run: str
    seq: int
    event: ActionDeclared
    state: GameState
    log: Sequence[LoggedEvent]
    index: int
    recent: list[AnyEvent]

    @property
    def id(self) -> str:
        return f"{self.run}:{self.seq}"


def run_names() -> list[str]:
    return sorted(p.name for p in FIXTURES.iterdir() if (p / "events.jsonl.gz").is_file())


def load_run(run: str) -> tuple[GameState, list[LoggedEvent]]:
    folder = FIXTURES / run
    initial = GameState.model_validate_json((folder / "initial.json").read_text("utf-8"))
    with gzip.open(folder / "events.jsonl.gz", "rt", encoding="utf-8") as raw:
        log = [LoggedEvent.model_validate_json(line) for line in raw if line.strip()]
    return initial, log


def walk(run: str, only: frozenset[int] | None = None) -> Iterator[Line]:
    """Each declared line of `run` (or just the seqs in `only`) with the state before it."""
    state, log = load_run(run)
    recent: list[AnyEvent] = []
    for index, entry in enumerate(log):
        event = entry.event
        if isinstance(event, ActionDeclared) and (only is None or entry.seq in only):
            yield Line(run, entry.seq, event, state, log, index, recent[-RECENT:])
        apply(state, event)
        recent.append(event)


@cache
def _regs() -> CombatRegistries:
    return combat_registries()


@cache
def _trade() -> TradeData:
    return TradeData(item_catalogue(), shop_table())


def menu_for(state: GameState, actor_id: str) -> ActionMenu:
    return build_menu(state, actor_id, _regs(), _trade())


def regs() -> CombatRegistries:
    return _regs()
