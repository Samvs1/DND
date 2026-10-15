"""M20.7 readable lines at the table: `narration_chunk` carries `line` and `speaker`, and the story
history for reconnects keeps each line and the speech on its own line ("\\n")."""

import asyncio
from pathlib import Path

from aidm.dm.guard_flow import GuardedSentences
from aidm.dm.guard_types import GuardReport
from aidm.dm.narration_stream import NarrationStream
from aidm.models.narration import NarrationTone
from aidm.models.protocol_server import NarrationChunkMsg
from aidm.session.table_core import TableConfig, TableCore
from aidm.session.telling import tell, tell_text
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import disabled_llm

LINES = ["Slendee gains True Strike.", "2 Giant Rats are surprised."]


def _core() -> TableCore:
    core = TableCore(inn_state(), disabled_llm(Path(".")), TableConfig(tts_enabled=False))
    core.conn_player["c1"] = "p1"
    core.outboxes["c1"] = asyncio.Queue()
    return core


def _chunks(core: TableCore) -> list[NarrationChunkMsg]:
    box = core.outboxes["c1"]
    out: list[NarrationChunkMsg] = []
    while not box.empty():
        msg = box.get_nowait()
        if isinstance(msg, NarrationChunkMsg):
            out.append(msg)
    return out


def _template(lines: list[str]) -> GuardedSentences:
    return GuardedSentences(None, lambda s: GuardReport(), lines)


async def test_template_lines_reach_the_table_as_lines() -> None:
    core = _core()
    text = await tell(core, NarrationStream(NarrationTone.COMBAT, _template(LINES)))
    assert text == " ".join(LINES)
    assert [(c.text, c.line, c.speaker) for c in _chunks(core)] == [
        (LINES[0], True, None),
        (LINES[1], True, None),
    ]
    told = [e for e in core.public.history().entries if e.kind == "narration"]
    assert told[-1].text == "\n".join(LINES)


async def test_engine_statements_and_silent_voice_are_lines() -> None:
    core = _core()
    await tell_text(core, "Slendee helps Ezra up.")
    voice = NarrationStream(NarrationTone.SOCIAL, _template(["Mira is silent."]), speaker="Mira")
    await tell(core, voice)
    got = _chunks(core)
    assert [(c.text, c.line, c.speaker) for c in got] == [
        ("Slendee helps Ezra up.", True, None),
        ("Mira is silent.", True, None),
    ]
