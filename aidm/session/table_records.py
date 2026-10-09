"""Records the table actor keeps between messages (split out of `table_core`, M11.2).

`PendingHostile`: a point-of-no-return tool call waiting for the acting player's confirmation
(`explore.confirm_hostile`). `OpenVote`: the open ready vote (`votes`) and its public view.
`TurnClock`: the running combat turn clock (`session.turn_clock`, M15.1): the end timer, the
30 s warning timer and the deadline the countdown is shown from.

Public API: `PendingHostile`, `OpenVote`, `TurnClock`.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from aidm.dm.llm_types import ToolCall
from aidm.models.protocol_views import VoteKind, VoteView
from aidm.session.table_clock import TimerHandle

type VoteJob = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class PendingHostile:
    player_id: str
    actor_id: str
    call: ToolCall
    prompt: str


@dataclass
class OpenVote:
    id: str
    kind: VoteKind
    detail: str
    proposer_id: str
    voters: list[str]
    on_pass: VoteJob
    ready: set[str] = field(default_factory=set[str])
    declined: set[str] = field(default_factory=set[str])
    seconds: float = 0.0
    timer: TimerHandle | None = None

    def view(self) -> VoteView:
        return VoteView(
            vote_id=self.id,
            kind=self.kind,
            detail=self.detail,
            proposer_id=self.proposer_id,
            voters=tuple(self.voters),
            ready=tuple(sorted(self.ready)),
            declined=tuple(sorted(self.declined)),
            seconds=self.seconds,
        )


@dataclass
class TurnClock:
    end: TimerHandle | None = None
    warn: TimerHandle | None = None
    deadline: float | None = None  # clock time the turn runs out (None: no countdown shown)

    def stop(self) -> None:
        for timer in (self.end, self.warn):
            if timer is not None:
                timer.cancel()
        self.end = self.warn = self.deadline = None
