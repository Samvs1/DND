"""The narration stream: guarded sentences as tone-tagged chunks (SPEC 6.1 step 3, 11).

`NarrationStream` is an async iterator of `NarrationChunk(index, text, tone, line, speaker)`,
one complete sentence each, so TTS can synthesise sentence N+1 while N plays. The sentences come
from `aidm.dm.guard_flow.GuardedSentences` (model stream, guard per sentence, one retry,
template fallback); this class numbers them, tags the scene tone and marks (M20.7):
- `line`: a template sentence (an engine statement such as "Slendee gains True Strike."), which
  the screen and the phone show on its own line; model prose stays one paragraph;
- `speaker`: an NPC's spoken reply (`NarrationStream(..., speaker=name)`). The engine strips the
  model's double quote marks (`speech_text`) and the reply reads once as `Name: "..."`; a
  template line in a voice stream (the silent fallback) is narration, never quoted, and so is a
  model sentence outside the reply's own quotes ('"Leave." Mira smiles.': the smile).

`text` is the whole narration as one string (memory, logs); `feed_text` keeps each line and the
speech on its own line ("\\n" between segments; the story history for reconnects).

Public API (`NarrationTone` lives in `aidm.models.narration`): `NarrationChunk`,
`NarrationStream(tone, sentences, *, speaker=None)` (`chunks`, `text`, `feed_text`, `source`,
`failure`, `reports`, `retried`, `collect()`), `speech_text(sentence)`, `QUOTE_MARKS`.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from aidm.dm.guard_flow import GuardedSentences, NarrationSource
from aidm.dm.guard_types import GuardReport
from aidm.dm.llm_types import LlmFailure
from aidm.models.narration import NarrationTone

QUOTE_MARKS = '"“”„‟«»″'


def speech_text(sentence: str) -> str:
    """The spoken words without the model's double quote marks (opened, closed or unbalanced)."""
    return " ".join(sentence.translate({ord(q): None for q in QUOTE_MARKS}).split())


@dataclass(frozen=True)
class NarrationChunk:
    index: int
    text: str
    tone: NarrationTone
    line: bool = False
    speaker: str | None = None


def _segments(chunks: list[NarrationChunk]) -> list[str]:
    """Paragraph segments: a run of prose, one line, or one speaker's quoted reply."""
    out: list[str] = []
    run: list[str] = []
    who: str | None = None
    for chunk in chunks:
        if run and (chunk.line or chunk.speaker != who):
            out.append(_said(who, run))
            run = []
        if chunk.line:
            out.append(chunk.text)
            continue
        who = chunk.speaker
        run.append(chunk.text)
    if run:
        out.append(_said(who, run))
    return out


def _said(speaker: str | None, sentences: list[str]) -> str:
    words = " ".join(sentences)
    return f'{speaker}: "{words}"' if speaker else words


class NarrationStream:
    def __init__(
        self, tone: NarrationTone, sentences: GuardedSentences, *, speaker: str | None = None
    ) -> None:
        self.tone = tone
        self.speaker = speaker
        self._sentences = sentences
        self.chunks: list[NarrationChunk] = []
        self._quoted = False  # the model's reply has used quote marks
        self._inside = False  # an opened quote is still open

    @property
    def text(self) -> str:
        return " ".join(_segments(self.chunks))

    @property
    def feed_text(self) -> str:
        return "\n".join(_segments(self.chunks))

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

    def _spoken(self, sentence: str) -> bool:
        """Spoken words, unless the reply quotes its speech and this sentence lies outside the
        quotes ('"The well? Old stones." Mira smiles.': the smile is narration)."""
        marks = sum(sentence.count(q) for q in QUOTE_MARKS)
        opened = self._inside
        self._quoted = self._quoted or marks > 0
        self._inside = opened != (marks % 2 == 1)
        return marks > 0 or opened or not self._quoted

    async def _run(self) -> AsyncIterator[NarrationChunk]:
        async for sentence in self._sentences:
            start = self._sentences.template_start
            line = start is not None and len(self._sentences.sentences) > start
            spoken = self.speaker is not None and not line and self._spoken(sentence)
            speaker = self.speaker if spoken else None
            text = speech_text(sentence) if self.speaker is not None and not line else sentence
            if not text:
                continue
            chunk = NarrationChunk(len(self.chunks), text, self.tone, line, speaker)
            self.chunks.append(chunk)
            yield chunk
