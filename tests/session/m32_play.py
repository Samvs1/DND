"""Shared helper of the M32.1a tests: one typed line played on a real round-5 state (fixtures
m32-r5-typed, m32-r5-quests, m32-r5-full; tests/session/playtest_saves.py) with the storyteller
disabled, so only the engine's own paths act."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from aidm.dm.fake_llm import FakeStep
from aidm.models.events import AnyEvent
from aidm.models.protocol import AnyClientMsg, AnyServerMsg
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import (
    ErrorMsg,
    NarrationChunkMsg,
    Notice,
    PendingConfirmationMsg,
)
from aidm.models.state import GameState
from tests.session.playtest_saves import logged, replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, menu_llm, running

TYPED = "m32-r5-typed"
QUESTS = "m32-r5-quests"
FULL = "m32-r5-full"


@dataclass
class Played:
    events: list[AnyEvent]
    state: GameState
    msgs: list[AnyServerMsg] = field(default_factory=list[AnyServerMsg])

    def notices(self) -> list[str]:
        return [m.text for m in self.msgs if isinstance(m, Notice | ErrorMsg)]

    def told(self) -> str:
        return " ".join(m.text for m in self.msgs if isinstance(m, NarrationChunkMsg))

    def asked(self) -> list[str]:
        return [m.prompt for m in self.msgs if isinstance(m, PendingConfirmationMsg)]

    def of[E](self, kind: type[E]) -> list[E]:
        return [e for e in self.events if isinstance(e, kind)]


def typed(run: str, seq: int) -> tuple[str, str]:
    event = logged(run, seq).event
    assert event.type == "action_declared"
    return event.creature_id, event.text


async def play(
    tmp_path: Path,
    run: str,
    seq: int,
    text: str | None = None,
    then: tuple[AnyClientMsg, ...] = (),
    *,
    picks: Sequence[FakeStep] | None = None,
) -> Played:
    """Seat a player as the hero who typed at `seq`, send the line (or `text`), then `then`.
    M36.10a: `picks` plays at the menu interpreter, the chooser's readings scripted (FakeLLM
    `by_tool`) and every other AI call failing as with no key."""
    actor, said = typed(run, seq)
    llm = disabled_llm(tmp_path)
    if picks is not None:
        llm = menu_llm(tmp_path, *picks, storyteller_down=True)[0]
    reading = None if picks is None else "menu"  # None: the table's default
    async with running(llm, replay_until(run, seq), interpreter=reading) as (table, _):
        seat = await join(table, "Ann", actor)
        seat.drain()
        start = table.state.event_count
        msgs: list[AnyServerMsg] = []
        for msg in (SubmitAction(text=text if text is not None else said), *then):
            seat.send(msg)
            await table.settle()
            msgs += seat.drain()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
        return Played(events, table.state, msgs)
