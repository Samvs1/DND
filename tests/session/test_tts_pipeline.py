"""The sentence TTS pipeline with a fake TTS hook: order, pipelining, fail-soft, toggle (M8.2)."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import GuardReport
from aidm.dm.llm_types import LlmFailure
from aidm.dm.narration_stream import NarrationChunk, NarrationStream
from aidm.models.narration import NarrationTone
from aidm.models.protocol import AnyServerMsg
from aidm.models.protocol_server import NarrationChunkMsg, NarrationDone
from aidm.session.table_core import TableConfig, TableCore
from aidm.session.telling import tell, tell_text
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import disabled_llm


class ListStream(NarrationStream):
    """A narration stream over fixed sentences (no model)."""

    def __init__(self, sentences: list[str], tone: NarrationTone = NarrationTone.SOCIAL) -> None:
        self.tone = tone
        self.chunks = []
        self._texts = sentences

    @property
    def source(self) -> NarrationSource:
        return NarrationSource.TEMPLATE

    @property
    def failure(self) -> LlmFailure | None:
        return None

    @property
    def reports(self) -> list[GuardReport]:
        return []

    @property
    def retried(self) -> bool:
        return False

    async def _run(self) -> AsyncIterator[NarrationChunk]:
        for text in self._texts:
            chunk = NarrationChunk(len(self.chunks), text, self.tone)
            self.chunks.append(chunk)
            await asyncio.sleep(0)
            yield chunk


class FakeTts:
    """A TTS hook that records calls and lets a test hold each sentence's synthesis open."""

    def __init__(self, hold: set[str] | None = None, fail: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.finished: list[str] = []
        self.gates = {text: asyncio.Event() for text in (hold or set())}
        self.fail = fail or set()

    async def __call__(self, text: str, tone: NarrationTone) -> str | None:
        self.calls.append(text)
        gate = self.gates.get(text)
        if gate is not None:
            await gate.wait()
        if text in self.fail:
            raise RuntimeError("synthesis exploded")
        self.finished.append(text)
        return f"/tts/{text[:1] * 40}.mp3"


def make_core(tts: FakeTts, *, enabled: bool = True, wait_s: float = 5.0) -> TableCore:
    config = TableConfig(tts=tts, tts_enabled=enabled, tts_wait_s=wait_s)
    core = TableCore(inn_state(), disabled_llm(Path(".")), config)
    core.conn_player["c1"] = "p1"
    core.outboxes["c1"] = asyncio.Queue()
    return core


def sent(core: TableCore) -> list[AnyServerMsg]:
    box = core.outboxes["c1"]
    out: list[AnyServerMsg] = []
    while not box.empty():
        out.append(box.get_nowait())
    return out


def chunks_of(msgs: list[AnyServerMsg]) -> list[NarrationChunkMsg]:
    return [m for m in msgs if isinstance(m, NarrationChunkMsg)]


async def test_chunks_carry_audio_in_order() -> None:
    tts = FakeTts()
    core = make_core(tts)
    text = await tell(core, ListStream(["Alpha one.", "Beta two.", "Gamma three."]))
    assert text == "Alpha one. Beta two. Gamma three."
    msgs = sent(core)
    got = chunks_of(msgs)
    assert [c.index for c in got] == [0, 1, 2]
    assert [c.text for c in got] == ["Alpha one.", "Beta two.", "Gamma three."]
    assert [c.audio_url for c in got] == [f"/tts/{x * 40}.mp3" for x in "ABG"]
    assert isinstance(msgs[-1], NarrationDone) and tts.calls == [c.text for c in got]


async def test_next_sentence_is_synthesised_while_the_first_is_pending() -> None:
    tts = FakeTts(hold={"Alpha one.", "Beta two."})
    core = make_core(tts)
    task = asyncio.create_task(tell(core, ListStream(["Alpha one.", "Beta two.", "Gamma three."])))
    for _ in range(20):
        await asyncio.sleep(0)
    # Nothing was sent (chunk 0 waits for its audio) but sentences 1 and 2 are already rendering.
    assert tts.calls == ["Alpha one.", "Beta two.", "Gamma three."]
    assert tts.finished == ["Gamma three."] and sent(core) == []
    tts.gates["Beta two."].set()
    await asyncio.sleep(0.01)
    assert sent(core) == []  # order is kept: chunk 1 does not overtake chunk 0
    tts.gates["Alpha one."].set()
    await task
    got = chunks_of(sent(core))
    assert [c.index for c in got] == [0, 1, 2] and all(c.audio_url for c in got)


async def test_synthesis_failure_gives_text_only_and_the_story_goes_on() -> None:
    tts = FakeTts(fail={"Beta two."})
    core = make_core(tts)
    await tell(core, ListStream(["Alpha one.", "Beta two.", "Gamma three."]))
    got = chunks_of(sent(core))
    assert [c.text for c in got] == ["Alpha one.", "Beta two.", "Gamma three."]
    assert [c.audio_url is None for c in got] == [False, True, False]


async def test_slow_synthesis_is_dropped_after_the_wait() -> None:
    tts = FakeTts(hold={"Alpha one."})
    core = make_core(tts, wait_s=0.05)
    await tell(core, ListStream(["Alpha one.", "Beta two."]))
    got = chunks_of(sent(core))
    assert [c.audio_url is None for c in got] == [True, False]


async def test_toggle_off_makes_no_synthesis_calls() -> None:
    tts = FakeTts()
    core = make_core(tts, enabled=False)
    await tell(core, ListStream(["Alpha one.", "Beta two."]))
    await tell_text(core, "Single line.")
    assert tts.calls == []
    got = chunks_of(sent(core))
    assert len(got) == 3 and all(c.audio_url is None for c in got)


async def test_toggle_is_read_live_and_tell_text_has_audio() -> None:
    tts = FakeTts()
    core = make_core(tts, enabled=False)
    core.tts_enabled = True
    await tell_text(core, "Single line.", NarrationTone.COMBAT)
    got = chunks_of(sent(core))
    assert [c.tone for c in got] == [NarrationTone.COMBAT] and got[0].audio_url is not None
