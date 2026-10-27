"""Contract rule D1 (the storyteller is told the turn's outcome, M43.3): the reason of every
`action_impossible` appears in the prompt rebuilt for the next `narration_recorded`.

The prompt is rebuilt with the current builder, as the narration audit does
(`scripts.audit.replay.build_prompt`), on the state before that narration. The refusal events
themselves are left out of the events the rebuild hands over: the session does not hand every
refusal to the narrator as an event (M43.2 logs menu refusals outside the told events), so D1
holds only when the builder carries them itself. A refusal no narration follows is not judged.
"""

from aidm.models.events import AnyEvent
from aidm.models.impossible import ActionImpossible
from aidm.models.state import GameState
from aidm.models.world_events import ActionDeclared, NarrationRecorded
from scripts.audit.replay import build_prompt
from scripts.contractlib.save import Finding


class TurnOutcomes:
    """D1: refusals since the last narration, judged against the next narration's prompt."""

    def __init__(self) -> None:
        self.segment: list[AnyEvent] = []
        self.refused: list[tuple[int, ActionImpossible]] = []
        self.line: tuple[str | None, str | None] = (None, None)

    def see(self, seq: int, state: GameState, event: AnyEvent) -> list[Finding]:
        if isinstance(event, NarrationRecorded):
            found = self._judge(state) if self.refused else []
            self.segment, self.refused = [], []
            return found
        if isinstance(event, ActionDeclared):
            self.line = (event.creature_id, event.text)
        elif isinstance(event, ActionImpossible):
            self.refused.append((seq, event))
        else:
            self.segment.append(event)
        return []

    def _judge(self, state: GameState) -> list[Finding]:
        try:
            prompt = build_prompt(state, self.segment, *self.line)
        except (KeyError, ValueError, AttributeError):
            return []  # the audit skips such a prompt too
        return [
            Finding("D1", seq, f"reason not told: {e.reason[:60]!r}")
            for seq, e in self.refused
            if e.reason.strip().rstrip(".") not in prompt
        ]

    def end(self, state: GameState) -> list[Finding]:
        return []
