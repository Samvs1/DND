"""Shared helper of the M36.6 menu-interpreter session tests: one typed line played at a real table
(`TableConfig.interpreter="menu"`) on a replayed round-6 state, the chooser's pick scripted with
FakeLLM `by_tool` steps (never the network), the storyteller on FakeLLM's defaults. Every play
asserts that replaying the log equals the snapshot."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aidm.dm.fake_llm import FakeLLM, FakeStep, fake_tool_call
from aidm.dm.llm_types import LlmMode
from aidm.models.events import AnyEvent
from aidm.models.protocol import AnyClientMsg, AnyServerMsg
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import ErrorMsg, Notice, NoticeKind
from aidm.models.state import GameState
from aidm.session import combat_flow
from aidm.session.session_log import SessionLog
from tests.ai.chooser_fixtures import chooser_client, state_at
from tests.session.m32_play import typed
from tests.session.table_fixtures import assert_replays, join, running

TYPED, QUESTS, FULL = "m35-r6-typed", "m35-r6-quests", "m35-r6-full"
type Step = tuple[str, Sequence[str], int | None]


def pick(*steps: Step, other: str | None = None, first: bool = False, colour: str = "") -> FakeStep:
    """The chooser's scripted answer: steps `(entry id, target ids, qty)`, and/or `other`;
    `colour` the words that only colour the steps (M36.9)."""
    rows = [{"do": e, "to": list(t), "qty": q} for e, t, q in steps]
    off: dict[str, Any] | None = None if other is None else {"text": other, "first": first}
    return fake_tool_call("choose_actions", {"steps": rows, "other": off, "colour": colour})


@dataclass
class MenuPlayed:
    events: list[AnyEvent]
    state: GameState
    fake: FakeLLM
    msgs: list[AnyServerMsg] = field(default_factory=list[AnyServerMsg])

    def notices(self) -> list[str]:
        return [m.text for m in self.msgs if isinstance(m, Notice | ErrorMsg)]

    def kinds(self) -> list[NoticeKind]:
        return [m.kind for m in self.msgs if isinstance(m, Notice)]

    def of[E](self, kind: type[E]) -> list[E]:
        return [e for e in self.events if isinstance(e, kind)]

    def choose_calls(self) -> int:
        return sum(1 for r in self.fake.requests if r.tool_choice == "choose_actions")


async def menu_play(
    tmp_path: Path,
    run: str,
    seq: int,
    *choices: FakeStep,
    text: str | None = None,
    actor: str | None = None,
    then: tuple[AnyClientMsg, ...] = (),
    prep: Callable[[GameState], None] | None = None,
    mode: LlmMode = LlmMode.FAKE,
    script: Sequence[FakeStep] = (),
    also: tuple[str, ...] = (),
    log: SessionLog | None = None,
) -> MenuPlayed:
    """Seat a player as the hero who typed at `seq` (or `actor`), send the line (or `text`).
    `also` seats other players first (their heroes' turns wait for them). On a fight state the
    active turn is opened first (`combat_flow.advance`)."""
    hero, said = typed(run, seq)
    state = state_at(run, seq).model_copy(deep=True)
    if prep is not None:
        prep(state)
    by_tool: Mapping[str, Sequence[FakeStep]] = {"choose_actions": choices}
    llm, fake = chooser_client(tmp_path, by_tool, script, mode=mode)
    async with running(llm, state, interpreter="menu", session_log=log) as (table, _):
        for n, other in enumerate(also):
            await join(table, f"Bo{n}", other)
        seat = await join(table, "Ann", actor or hero)
        if table.combat_active():  # a fight state: open the active turn first
            table.in_combat = True
            table.schedule(lambda: combat_flow.advance(table))
            await table.settle()
        seat.drain()
        start = table.state.event_count
        msgs: list[AnyServerMsg] = []
        for msg in (SubmitAction(text=text if text is not None else said), *then):
            seat.send(msg)
            await table.settle()
            msgs += seat.drain()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
        return MenuPlayed(events, table.state, fake, msgs)
