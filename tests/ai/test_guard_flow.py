"""Guarded narration flow over FakeLLM (M4.6, SPEC 6.1 step 4, 6.5): retry once, then template."""

from pathlib import Path

from aidm.dm.fake_llm import FakeStream, fake_text
from aidm.dm.guard import (
    CONTINUE_NOTE,
    SCRUB_TOKEN,
    guarded_narration,
    prose_checker,
    retry_messages,
    scrub_messages,
)
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import GuardReport, Violation, ViolationKind
from aidm.dm.narration_templates import QUIET_LINE
from aidm.dm.narrator import narrate
from aidm.dm.sentence_chunker import strip_markdown
from tests.ai.fake_scripts import (
    crowd_plural_narration,
    fake_client,
    invented_feature_narration,
    invented_people_narration,
)
from tests.ai.guard_fixtures import inn_state

CLEAN = "Mira smiles and slides a mug across the bar. Aria thanks her."


def _user_text(messages: list[dict[str, object]]) -> str:
    return "\n".join(str(m["content"]) for m in messages if m["role"] != "system")


async def test_hallucination_retry_still_bad_then_template(tmp_path: Path) -> None:
    state = inn_state()
    state.memory.narration = ["Sister Kelene greeted you at the gate."]
    script = [invented_people_narration(), invented_people_narration()]
    client, fake = fake_client(tmp_path, script)
    stream = narrate(state, [], client)
    text = await stream.collect()
    assert "Kelene" not in text and text == QUIET_LINE
    assert stream.source is NarrationSource.TEMPLATE and stream.retried
    assert len(fake.requests) == 2 and len(stream.reports) == 2
    first, second = (list(r.messages) for r in fake.requests)
    assert "Kelene" in _user_text(first)
    retry = _user_text(second)
    assert "Kelene" not in retry and SCRUB_TOKEN in retry and "ENGINE GUARD" in retry


async def test_hallucination_then_clean_retry_is_used(tmp_path: Path) -> None:
    client, fake = fake_client(tmp_path, [invented_feature_narration(), fake_text(CLEAN)])
    stream = narrate(inn_state(), [], client)
    assert await stream.collect() == CLEAN
    assert stream.source is NarrationSource.MODEL and stream.retried
    assert stream.reports[0].violations[0].kind is ViolationKind.UNLISTED_FEATURE
    assert len(fake.requests) == 2


async def test_mid_stream_violation_retry_continues_after_shown_text(tmp_path: Path) -> None:
    first = FakeStream(("Mira nods. Aria sits. ", "Sister Kelene waves from the stair."))
    client, fake = fake_client(tmp_path, [first, fake_text("The fire crackles.")])
    stream = narrate(inn_state(), [], client)
    texts = [c.text async for c in stream]
    assert texts == ["Mira nods.", "Aria sits.", "The fire crackles."]
    retry = list(fake.requests[1].messages)
    assert retry[-2] == {"role": "assistant", "content": "Mira nods. Aria sits."}
    assert CONTINUE_NOTE in str(retry[-1]["content"])


async def test_mid_stream_violation_twice_appends_template_ending(tmp_path: Path) -> None:
    first = FakeStream(("Mira nods. ", "A throng of onlookers cheers."))
    client, _ = fake_client(tmp_path, [first, crowd_plural_narration()])
    state = inn_state()
    state.world.npcs.pop("npc-hobb")
    stream = narrate(state, [], client)
    texts = [c.text async for c in stream]
    assert texts == ["Mira nods.", QUIET_LINE]
    assert stream.source is NarrationSource.MIXED and len(stream.reports) == 2


async def test_guarded_narration_serves_npc_speech(tmp_path: Path) -> None:
    state = inn_state()
    client, _ = fake_client(tmp_path, [invented_people_narration(), invented_people_narration()])
    messages = [{"role": "system", "content": "Speak as Mira."}, {"role": "user", "content": "Hi"}]
    speech = guarded_narration(client, messages, prose_checker(state), ['"Welcome, travellers."'])
    assert await speech.collect() == '"Welcome, travellers."'
    assert speech.source is NarrationSource.TEMPLATE and speech.retried


def test_scrub_messages_keeps_system_and_word_boundaries() -> None:
    messages = [
        {"role": "system", "content": "Never name Kelene."},
        {"role": "user", "content": "Kelene's lamp; Kelenes; kelene waits."},
    ]
    out = scrub_messages(messages, ["Kelene"])
    assert out[0] == messages[0]
    assert out[1]["content"] == f"{SCRUB_TOKEN}'s lamp; Kelenes; {SCRUB_TOKEN} waits."
    assert messages[1]["content"].startswith("Kelene")


def test_retry_messages_never_repeat_a_scrubbed_name() -> None:
    report = GuardReport(
        (
            Violation(ViolationKind.UNKNOWN_NAME, "Kelene", "Kelene is not in the manifest"),
            Violation(ViolationKind.DEAD_ACTING, "Gorrak", "Gorrak is dead and cannot act"),
        )
    )
    out = retry_messages([{"role": "user", "content": "Kelene and Gorrak"}], report, "")
    assert report.scrub_terms == ("Kelene",)
    text = _user_text(out)
    assert "Kelene" not in text and "Gorrak is dead" in text and CONTINUE_NOTE not in text


async def test_qa_12_retry_continues_instead_of_retelling(tmp_path: Path) -> None:
    first = FakeStream(
        (
            "Mira leans across the long oak bar and lowers her voice to a whisper. ",
            "Sister Kelene waves from the stair.",
        )
    )
    retold = fake_text(
        "Mira leans over the long oak bar, lowering her voice to a whisper. "
        "She slides a mug of cider toward Aria."
    )
    client, fake = fake_client(tmp_path, [first, retold])
    stream = narrate(inn_state(), [], client)
    texts = [c.text async for c in stream]
    assert texts == [
        "Mira leans across the long oak bar and lowers her voice to a whisper.",
        "She slides a mug of cider toward Aria.",
    ]
    note = str(list(fake.requests[1].messages)[-1]["content"])
    assert "Mira leans across the long oak bar" in note and "do not repeat" in note


async def test_qa_13_markdown_is_stripped_before_players_and_tts(tmp_path: Path) -> None:
    raw = "`Aria is no wizard, and no fire leaps from her hands.` The **inn** settles *quietly*."
    client, _ = fake_client(tmp_path, [fake_text(raw)])
    stream = narrate(inn_state(), [], client)
    texts = [c.text async for c in stream]
    assert texts == [
        "Aria is no wizard, and no fire leaps from her hands.",
        "The inn settles quietly.",
    ]
    assert strip_markdown("## The **Lantern** Inn") == "The Lantern Inn"
