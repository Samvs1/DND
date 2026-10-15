"""M20.7 readable lines (playtest 3, D9 and D10): template statements are flagged as lines,
conditions read by display name in plain words, NPC speech reads once as `Name: "..."`, and the
narrator is told not to speak for the NPC who answers next."""

from pathlib import Path

from aidm.dm.event_text import event_line
from aidm.dm.fake_llm import FakeStream, fake_text
from aidm.dm.guard import guarded_narration
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import GuardReport, Violation, ViolationKind
from aidm.dm.narration_stream import NarrationStream, speech_text
from aidm.dm.narration_templates import CLOSING_LINE, template_line, template_narration
from aidm.dm.narrator import VOICE_NEXT, narrate
from aidm.models.events import AnyEvent, ConditionApplied, ConditionRemoved
from aidm.models.narration import NarrationTone
from aidm.models.state import ActiveCondition, GameState
from tests.ai.fake_scripts import fake_client
from tests.ai.guard_fixtures import add_dead, inn_state

MESSAGES = [{"role": "user", "content": "tell it"}]
FALLBACK = ["Slendee strikes Goblin A.", "Goblin A is wounded."]


def _gains(cid: str, name: str) -> ConditionApplied:
    return ConditionApplied(creature_id=cid, condition=ActiveCondition(name=name))


def _rats() -> GameState:
    state = inn_state()
    add_dead(state, "slendee", "Slendee", dead=False)
    add_dead(state, "giant-rat-1", "Giant Rat A", dead=False)
    add_dead(state, "giant-rat-2", "Giant Rat B", dead=False)
    return state


def _flag_kelene(sentence: str) -> GuardReport:
    if "Kelene" not in sentence:
        return GuardReport()
    return GuardReport((Violation(ViolationKind.UNKNOWN_NAME, "Kelene", "not here"),))


def test_golden_condition_lines_use_display_names() -> None:
    state = _rats()
    gains = _gains("slendee", "true-strike")
    ends = ConditionRemoved(creature_id="giant-rat-1", name="hunters-mark")
    prone = ConditionRemoved(creature_id="slendee", name="prone")
    # Display names from data/bg3/conditions.json ("True Strike", "Hunter's Mark").
    assert template_line(state, gains) == event_line(state, gains) == "Slendee gains True Strike."
    assert event_line(state, ends) == "Hunter's Mark ends for Giant Rat A."
    assert template_line(state, prone) == "Slendee is no longer prone."
    assert event_line(state, _gains("slendee", "surprised")) == "Slendee is surprised."


def test_golden_one_condition_on_many_reads_once() -> None:
    state = _rats()
    events: list[AnyEvent] = [
        _gains("giant-rat-1", "surprised"),
        _gains("giant-rat-2", "surprised"),
    ]
    assert template_narration(events, state) == ["2 Giant Rats are surprised."]
    mixed: list[AnyEvent] = [_gains("giant-rat-1", "bane"), _gains("slendee", "bane")]
    assert template_narration(mixed, state) == ["Giant Rat A and Slendee gain Bane."]


async def test_template_sentences_are_flagged_as_lines(tmp_path: Path) -> None:
    client, _ = fake_client(tmp_path, [FakeStream(())])
    sentences = guarded_narration(client, MESSAGES, lambda s: GuardReport(), FALLBACK)
    stream = NarrationStream(NarrationTone.COMBAT, sentences)
    chunks = [chunk async for chunk in stream]
    assert stream.source is NarrationSource.TEMPLATE
    assert [(c.text, c.line) for c in chunks] == [(FALLBACK[0], True), (FALLBACK[1], True)]
    assert stream.feed_text == "\n".join(FALLBACK) and stream.text == " ".join(FALLBACK)


async def test_model_prose_stays_a_paragraph_and_the_closing_line_stands_alone(
    tmp_path: Path,
) -> None:
    prose = FakeStream(("Mira nods. Aria sits. ", "Sister Kelene waves from the stair."))
    still = FakeStream(("Sister Kelene waves again.",))
    client, _ = fake_client(tmp_path, [prose, still])
    sentences = guarded_narration(client, MESSAGES, _flag_kelene, FALLBACK)
    stream = NarrationStream(NarrationTone.EXPLORATION, sentences)
    chunks = [chunk async for chunk in stream]
    assert stream.source is NarrationSource.MIXED
    assert [(c.text, c.line) for c in chunks] == [
        ("Mira nods.", False),
        ("Aria sits.", False),
        (CLOSING_LINE, True),
    ]
    assert stream.feed_text == f"Mira nods. Aria sits.\n{CLOSING_LINE}"


def test_speech_text_strips_double_quotes_only() -> None:
    assert speech_text('"Leave the lantern," ') == "Leave the lantern,"
    assert speech_text("“The water remembers.”") == "The water remembers."
    assert (
        speech_text("\"Unclosed, and the ferryman's coin.") == "Unclosed, and the ferryman's coin."
    )


async def test_npc_reply_reads_once_with_the_speaker(tmp_path: Path) -> None:
    reply = FakeStream(('"Leave the lantern. ', 'The water remembers." ', "Sellen turns away."))
    client, _ = fake_client(tmp_path, [reply])
    sentences = guarded_narration(client, MESSAGES, lambda s: GuardReport(), ["Sellen is silent."])
    stream = NarrationStream(NarrationTone.SOCIAL, sentences, speaker="Warden Sellen Ost")
    chunks = [chunk async for chunk in stream]
    assert [c.speaker for c in chunks] == ["Warden Sellen Ost", "Warden Sellen Ost", None]
    assert chunks[0].text == "Leave the lantern."  # the TTS reads the words, no quote marks
    said = 'Warden Sellen Ost: "Leave the lantern. The water remembers."'
    assert stream.feed_text == f"{said}\nSellen turns away."


async def test_npc_reply_without_quotes_and_the_silent_fallback(tmp_path: Path) -> None:
    client, _ = fake_client(tmp_path, [fake_text("Go home. It is late."), FakeStream(())])
    plain = guarded_narration(client, MESSAGES, lambda s: GuardReport(), ["Mira is silent."])
    stream = NarrationStream(NarrationTone.SOCIAL, plain, speaker="Mira")
    assert await stream.collect() == 'Mira: "Go home. It is late."'
    silent = guarded_narration(client, MESSAGES, lambda s: GuardReport(), ["Mira is silent."])
    fallback = NarrationStream(NarrationTone.SOCIAL, silent, speaker="Mira")
    assert await fallback.collect() == "Mira is silent."
    assert [c.line for c in fallback.chunks] == [True]


async def test_narrator_leaves_the_answer_to_the_npc(tmp_path: Path) -> None:
    client, fake = fake_client(tmp_path, [fake_text("Aria raises her mug to Mira.")])
    await narrate(inn_state(), [], client, voice_next="Mira").collect()
    sent = str(fake.requests[0].messages)
    assert VOICE_NEXT.format(name="Mira") in sent
