"""The guarded prose flow: model sentences, guard, one retry, template (SPEC 6.1, 6.5, 6.8).

`GuardedSentences` is an async iterator of complete sentences (`aidm.dm.sentence_chunker`).
Every sentence passes the `check` (`ProseCheck`) BEFORE it is yielded, so a flagged sentence
never reaches a player, TTS or memory. Flow:
1. attempt 1 streams; a flagged sentence stops it;
2. ONE regeneration: the attempt factory gets the guard report and the text already shown (the
   caller adds the correction and scrubs the offending names, `aidm.dm.guard.retry_messages`),
   and continues after the shown sentences; leading retry sentences that mostly retell a shown
   one (`repeats`, word overlap >= `REPEAT_OVERLAP`) are dropped (QA-12);
3. still flagged, or the model failed (disabled, timeout, transport, empty): the safe template.

Ending rules: nothing shown -> the whole template (`source` TEMPLATE); something shown but the
model stopped -> the unfinished fragment is dropped and the template lines follow when fewer
than `MIN_MODEL_SENTENCES` were shown (the outcome must be told), else `CLOSING_LINE` (`source`
MIXED; M31.1c V20: `closing` replaces it, the epilogue passes none). At most `MAX_SENTENCES`
sentences. `record` (M31.1c V20: the epilogue's engine-written quest list and who lived) is always
appended after the prose, whatever its source. `template_start` is the index of the first template
sentence (None while only model prose was shown): those are engine statements, shown each on its
own line (M20.7).

Public API: `NarrationSource`, `AttemptFactory`, `model_sentences(stream)`,
`GuardedSentences(attempt, check, fallback_lines, *, max_attempts, max_sentences, closing,
record)` (`sentences`,
`text`, `source`, `failure`, `reports`, `attempts`, `retried`, `template_start`, `collect()`),
`MAX_SENTENCES`,
`MIN_MODEL_SENTENCES`, `MAX_ATTEMPTS`, `REPEAT_OVERLAP`, `repeats(sentence, shown)`.
"""

import re
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Sequence
from enum import StrEnum

from aidm.dm.guard_types import GuardReport, ProseCheck
from aidm.dm.llm_client import TextStream
from aidm.dm.llm_types import LlmFailure
from aidm.dm.narration_templates import CLOSING_LINE
from aidm.dm.sentence_chunker import SentenceChunker, strip_markdown, strip_marks

MAX_SENTENCES = 8
MIN_MODEL_SENTENCES = 2
MAX_ATTEMPTS = 2
REPEAT_OVERLAP = 0.7


class NarrationSource(StrEnum):
    MODEL = "model"
    TEMPLATE = "template"
    MIXED = "mixed"


type AttemptFactory = Callable[[GuardReport | None, str], TextStream]


async def model_sentences(stream: TextStream) -> AsyncGenerator[str]:
    """Complete sentences of one model stream, markdown stripped (QA-13); an unfinished fragment
    after a failure is dropped."""
    chunker = SentenceChunker()
    pieces = aiter(stream)
    try:
        async for piece in pieces:
            for sentence in chunker.feed(strip_marks(piece)):
                if plain := strip_markdown(sentence):
                    yield plain
    finally:
        closer = getattr(pieces, "aclose", None)
        if closer is not None:
            await closer()
    if stream.failure is None:
        for sentence in chunker.flush():
            if plain := strip_markdown(sentence):
                yield plain


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", text.casefold()) if len(w) >= 3}


def repeats(sentence: str, shown: Sequence[str]) -> bool:
    """True when `sentence` mostly retells one of the `shown` sentences (word overlap)."""
    words = _words(sentence)
    if not words:
        return False
    for old in shown:
        seen = _words(old)
        if seen and len(words & seen) / min(len(words), len(seen)) >= REPEAT_OVERLAP:
            return True
    return False


class GuardedSentences:
    def __init__(
        self,
        attempt: AttemptFactory | None,
        check: ProseCheck,
        fallback_lines: Sequence[str],
        *,
        max_attempts: int = MAX_ATTEMPTS,
        max_sentences: int = MAX_SENTENCES,
        closing: Sequence[str] = (CLOSING_LINE,),
        record: Sequence[str] = (),
    ) -> None:
        self._attempt = attempt
        self._closing = list(closing)
        self._record = list(record)
        self._check = check
        self._fallback = list(fallback_lines)
        self._max_attempts = max_attempts
        self._max = max_sentences
        self._stopped: GuardReport | None = None
        self.sentences: list[str] = []
        self.reports: list[GuardReport] = []
        self.failure: LlmFailure | None = None
        self.attempts = 0
        self.source = NarrationSource.TEMPLATE
        self.template_start: int | None = None

    @property
    def text(self) -> str:
        return " ".join(self.sentences)

    @property
    def retried(self) -> bool:
        return self.attempts > 1

    def __aiter__(self) -> AsyncIterator[str]:
        return self._run()

    async def collect(self) -> str:
        async for _ in self:
            pass
        return self.text

    async def _once(
        self, attempt: AttemptFactory, previous: GuardReport | None
    ) -> AsyncIterator[str]:
        self.attempts += 1
        self._stopped = None
        stream = attempt(previous, self.text)
        sentences = model_sentences(stream)
        leading = previous is not None and bool(self.sentences)
        try:
            async for sentence in sentences:
                if leading and repeats(sentence, self.sentences):
                    continue  # the retry retold an already shown beat (QA-12)
                leading = False
                report = self._check(sentence)
                if not report.ok:
                    self.reports.append(report)
                    self._stopped = report
                    break
                self.sentences.append(sentence)
                yield sentence
                if len(self.sentences) >= self._max:
                    break
        finally:
            await sentences.aclose()
        self.failure = stream.failure

    async def _model(self) -> AsyncIterator[str]:
        attempt = self._attempt
        previous: GuardReport | None = None
        while attempt is not None and self.attempts < self._max_attempts:
            async for sentence in self._once(attempt, previous):
                yield sentence
            if self._stopped is None or len(self.sentences) >= self._max:
                return
            previous = self._stopped

    def _ending(self) -> list[str]:
        shown = len(self.sentences)
        clean = self.failure is None and self._stopped is None
        if shown and (clean or shown >= self._max):
            self.source = NarrationSource.MODEL
            return []
        self.source = NarrationSource.MIXED if shown else NarrationSource.TEMPLATE
        return self._fallback if shown < MIN_MODEL_SENTENCES else self._closing

    async def _run(self) -> AsyncIterator[str]:
        async for sentence in self._model():
            yield sentence
        ending = [*self._ending(), *self._record]
        if ending:
            self.template_start = len(self.sentences)
        for line in ending:
            self.sentences.append(line)
            yield line
