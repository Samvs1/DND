"""The sentence TTS pipeline: ordered `narration_chunk` broadcast with pipelined synthesis (M8.2).

`NarrationPipe.add(chunk)` starts the chunk's synthesis at once (when the host's TTS toggle is on)
and queues it; one sender task broadcasts the chunks IN ORDER, each holding for its audio for at
most `TableConfig.tts_wait_s`, then sends the chunk with `audio_url` (or without it when the
synthesis failed, timed out or TTS is off: the client then types the text). Sentence N+1 is
therefore being synthesised while N is awaited, sent and played. Text and audio stay aligned
because they travel in the same message. A TTS failure never raises and never delays a
mechanics broadcast (those happen before narration, in `core.apply`).

Public API: `NarrationPipe` (`add`, `finish`, `abort`).
"""

import asyncio
import logging

from aidm.dm.narration_stream import NarrationChunk
from aidm.models.protocol_server import NarrationChunkMsg
from aidm.session.table_core import TableCore

_LOG = logging.getLogger(__name__)
type _Item = tuple[NarrationChunk, asyncio.Task[str | None] | None] | None


class NarrationPipe:
    def __init__(self, core: TableCore, nid: str) -> None:
        self._core = core
        self._nid = nid
        self._queue: asyncio.Queue[_Item] = asyncio.Queue()
        self._sender = asyncio.create_task(self._run())

    def add(self, chunk: NarrationChunk) -> None:
        synth = None
        if self._core.tts_enabled:
            synth = asyncio.create_task(self._synthesize(chunk))
        self._queue.put_nowait((chunk, synth))

    async def finish(self) -> None:
        self._queue.put_nowait(None)
        await self._sender

    def abort(self) -> None:
        self._sender.cancel()
        while not self._queue.empty():
            item = self._queue.get_nowait()
            if item is not None and item[1] is not None:
                item[1].cancel()

    async def _synthesize(self, chunk: NarrationChunk) -> str | None:
        try:
            return await self._core.config.tts(chunk.text, chunk.tone)
        except Exception as exc:
            _LOG.warning("tts hook failed: %s", type(exc).__name__)
            return None

    async def _audio(self, synth: asyncio.Task[str | None] | None) -> str | None:
        if synth is None:
            return None
        try:
            return await asyncio.wait_for(synth, self._core.config.tts_wait_s)
        except TimeoutError:
            return None

    async def _run(self) -> None:
        while (item := await self._queue.get()) is not None:
            chunk, synth = item
            audio = await self._audio(synth)
            self._core.broadcast(
                NarrationChunkMsg(
                    id=self._nid,
                    index=chunk.index,
                    text=chunk.text,
                    audio_url=audio,
                    tone=chunk.tone,
                    line=chunk.line,
                    speaker=chunk.speaker,
                )
            )
