"""The narration stream: guarded sentences as tone-tagged chunks (SPEC 6.1 step 3, 11).

`NarrationStream` is an async iterator of `NarrationChunk(index, text, tone)`, one complete
sentence each, so TTS can synthesise sentence N+1 while N plays. The sentences come from
`aidm.dm.guard_flow.GuardedSentences` (model stream, guard per sentence, one retry, template
fallback); this class only numbers them and tags the scene tone.

Public API: `NarrationTone` (COMBAT / SOCIAL / EXPLORATION), `NarrationChunk`,
`NarrationStream(tone, sentences)` (`chunks`, `text`, `source`, `failure`, `reports`,
`retried`, `collect()`).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum

from aidm.dm.guard_flow import GuardedSentences, NarrationSource
from aidm.dm.guard_types import GuardReport
from aidm.dm.llm_types import LlmFailure


class NarrationTone(StrEnum):
    COMBAT = "combat"
    SOCIAL = "social"
    EXPLORATION = "exploration"


@dataclass(frozen=True)
class NarrationChunk:
    index: int
    text: str
    tone: NarrationTone


class NarrationStream:
    def __init__(self, tone: NarrationTone, sentences: GuardedSentences) -> None:
        self.tone = tone
        self._sentences = sentences
        self.chunks: list[NarrationChunk] = []

    @property
    def text(self) -> str:
        return " ".join(c.text for c in self.chunks)

    @property
    def source(self) -> NarrationSource:
        return self._sentences.source

    @property
    def failure(self) -> LlmFailure | None:
        return self._sentences.failure

    @property
    def reports(self) -> list[GuardReport]:
        return self._sentences.reports

    @property
    def retried(self) -> bool:
        return self._sentences.retried

    def __aiter__(self) -> AsyncIterator[NarrationChunk]:
        return self._run()

    async def collect(self) -> str:
        async for _ in self:
            pass
        return self.text

    async def _run(self) -> AsyncIterator[NarrationChunk]:
        async for sentence in self._sentences:
            chunk = NarrationChunk(len(self.chunks), sentence, self.tone)
            self.chunks.append(chunk)
            yield chunk
