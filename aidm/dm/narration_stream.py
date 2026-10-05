"""The narration stream: model sentences, guarded one by one, with fallbacks (SPEC 6.1, 6.8).

`NarrationStream` is an async iterator of `NarrationChunk(index, text, tone)`, one complete
sentence each (`aidm.dm.sentence_chunker`), so TTS can synthesise sentence N+1 while N plays.
Every sentence passes the `guard` hook (`ProseCheck`) BEFORE it is yielded, so a flagged sentence
never reaches a player.

Outcomes (never silent, never an empty narration):
- the model answers cleanly: its sentences (`source` MODEL), at most `MAX_SENTENCES`;
- the model is disabled, fails, times out or answers empty before any sentence: the template
  narration (`source` TEMPLATE);
- the model stops mid-stream (failure or a guard stop) after some sentences: the unfinished
  fragment is dropped and a graceful ending is appended (`source` MIXED): the full template
  lines when fewer than `MIN_MODEL_SENTENCES` model sentences were shown (the outcome must be
  told), else `CLOSING_LINE`.

Public API: `NarrationTone` (COMBAT / SOCIAL / EXPLORATION), `NarrationSource`,
`NarrationChunk`, `SentenceAttempt` (a factory for one model stream), `NarrationStream(tone,
attempt, template_lines, guard)` (`chunks`, `text`, `source`, `failure`, `reports`,
`collect()`), `MAX_SENTENCES`, `MIN_MODEL_SENTENCES`.
"""

from collections.abc import AsyncGenerator, AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from aidm.dm.guard_types import GuardReport, ProseCheck, no_guard
from aidm.dm.llm_client import TextStream
from aidm.dm.llm_types import LlmFailure
from aidm.dm.narration_templates import CLOSING_LINE
from aidm.dm.sentence_chunker import SentenceChunker

MAX_SENTENCES = 8
MIN_MODEL_SENTENCES = 2


class NarrationTone(StrEnum):
    COMBAT = "combat"
    SOCIAL = "social"
    EXPLORATION = "exploration"


class NarrationSource(StrEnum):
    MODEL = "model"
    TEMPLATE = "template"
    MIXED = "mixed"


@dataclass(frozen=True)
class NarrationChunk:
    index: int
    text: str
    tone: NarrationTone


type SentenceAttempt = Callable[[], TextStream]


async def model_sentences(stream: TextStream) -> AsyncGenerator[str]:
    """Complete sentences of one model stream; an unfinished fragment after a failure is dropped."""
    chunker = SentenceChunker()
    pieces = aiter(stream)
    try:
        async for piece in pieces:
            for sentence in chunker.feed(piece):
                yield sentence
    finally:
        closer = getattr(pieces, "aclose", None)
        if closer is not None:
            await closer()
    if stream.failure is None:
        for sentence in chunker.flush():
            yield sentence


class NarrationStream:
    def __init__(
        self,
        tone: NarrationTone,
        attempt: SentenceAttempt | None,
        template_lines: Sequence[str],
        guard: ProseCheck = no_guard,
    ) -> None:
        self.tone = tone
        self._attempt = attempt
        self._template = list(template_lines)
        self._guard = guard
        self.chunks: list[NarrationChunk] = []
        self.failure: LlmFailure | None = None
        self.reports: list[GuardReport] = []
        self.source = NarrationSource.TEMPLATE

    @property
    def text(self) -> str:
        return " ".join(c.text for c in self.chunks)

    def __aiter__(self) -> AsyncIterator[NarrationChunk]:
        return self._run()

    async def collect(self) -> str:
        async for _ in self:
            pass
        return self.text

    def _emit(self, text: str) -> NarrationChunk:
        chunk = NarrationChunk(len(self.chunks), text, self.tone)
        self.chunks.append(chunk)
        return chunk

    async def _model(self) -> AsyncIterator[NarrationChunk]:
        if self._attempt is None:
            return
        stream = self._attempt()
        sentences = model_sentences(stream)
        try:
            async for sentence in sentences:
                report = self._guard(sentence)
                if not report.ok:
                    self.reports.append(report)
                    break
                yield self._emit(sentence)
                if len(self.chunks) >= MAX_SENTENCES:
                    break
        finally:
            await sentences.aclose()
        self.failure = stream.failure

    async def _run(self) -> AsyncIterator[NarrationChunk]:
        async for chunk in self._model():
            yield chunk
        shown = len(self.chunks)
        clean = self.failure is None and not self.reports
        if shown and (clean or shown >= MAX_SENTENCES):
            self.source = NarrationSource.MODEL
            return
        self.source = NarrationSource.MIXED if shown else NarrationSource.TEMPLATE
        ending = self._template if shown < MIN_MODEL_SENTENCES else [CLOSING_LINE]
        for line in ending:
            yield self._emit(line)
