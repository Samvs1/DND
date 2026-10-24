"""M31.1c V17-V19 (docs/playtests/M31_round4.md): found things told taken, a gift told going to
someone else, a waiting quest offer told accepted, a keepsake hand-over left untold. Each test
replays a live round 4 save to the narration the model wrote, feeds its REAL text with that
beat's facts to THE guard and checks the kind flagged; the honest telling passes (FakeLLM only)."""

from pathlib import Path

from aidm.dm.event_text import event_line, event_notes
from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import prose_checker
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narrator import narrate
from aidm.models.quest_events import QuestAsked
from aidm.models.world_events import AttitudeChanged, ItemDiscovered, KeepsakeGained
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import ToldTurn, told_turn

K = ViolationKind


def _found(turn: ToldTurn, text: str | None = None) -> set[tuple[ViolationKind, str]]:
    check = prose_checker(
        turn.state, turn.events, actor_id=turn.actor_id, player_text=turn.player_text
    )
    return {(v.kind, v.span) for v in check(text if text is not None else turn.prose).violations}


def _kinds(turn: ToldTurn, text: str) -> set[ViolationKind]:
    return {kind for kind, _ in _found(turn, text)}


def _lines(turn: ToldTurn, kind: type) -> str:
    return " ".join(
        line
        for e in turn.events
        if isinstance(e, kind) and (line := event_line(turn.state, e)) is not None
    )


def test_m31_found_told_taken() -> None:
    """full 463, 605, 624: a search turned things up (ItemDiscovered) and nobody took them, but
    the prose has Rook come up with the ledger, draw both sprigs, tuck the herb away."""
    cases = [
        ("m31-r4-full", 463, "tucked into one arm"),
        ("m31-r4-full", 605, "draws both"),
        ("m31-r4-full", 624, "tucks it away"),
    ]
    for run, seq, span in cases:
        assert (K.FOUND_TAKEN, span) in _found(told_turn(run, seq)), (run, seq)
    turn = told_turn("m31-r4-full", 605)
    assert "nobody has picked it up" in _lines(turn, ItemDiscovered)


def test_m31_found_honest_version_passes() -> None:
    honest = (
        "Rook's search of the garden plots and ditches turns up two sprigs of grey moor-herb,"
        " their pale leaves still whole among the weeds. They lie in the damp soil, ready for"
        " the taking."
    )
    assert K.FOUND_TAKEN not in _kinds(told_turn("m31-r4-full", 605), honest)


def test_m31_gift_recipient() -> None:
    """full 544: Brienne gave the poultice to Sister Thena; the prose pressed it into the
    peddler's palm. The facts now name who received it."""
    turn = told_turn("m31-r4-full", 544)
    assert (K.WRONG_RECIPIENT, "peddler") in _found(turn)
    assert "Sister Thena received the gift (Herbal Poultice)" in _lines(turn, AttitudeChanged)
    honest = (
        "Brienne presses a herbal poultice into Sister Thena's palm, and the gesture loosens"
        " something in her guarded stance."
    )
    assert K.WRONG_RECIPIENT not in _kinds(turn, honest)


async def test_m31_offered_quest_not_accepted(tmp_path: Path) -> None:
    """V18 full 745: Warder Pell's offer waited for the players' answer (accepted only at 749),
    but the prose said "You accept Warder Pell's strange request". The facts say it waits; the
    guard flags the acceptance; after the real acceptance (750) "You take the errand" passes."""
    turn = told_turn("m31-r4-full", 745)
    assert (K.QUEST_ACCEPTED, "You accept") in _found(turn)
    assert "waiting for the players' answer" in _lines(turn, QuestAsked)
    honest = (
        "Warder Pell lays out his strange request before the lantern light settles, and waits"
        " for your answer while the flat ferry rocks once beneath you."
    )
    assert K.QUEST_ACCEPTED not in _kinds(turn, honest)
    assert not _found(told_turn("m31-r4-full", 750))
    client, fake = fake_client(tmp_path, [fake_text(turn.prose), fake_text(turn.prose)])
    stream = narrate(
        turn.state, list(turn.events), client, actor_id=turn.actor_id, player_text=None
    )
    text = await stream.collect()
    assert stream.source is not NarrationSource.MODEL and "You accept" not in text
    assert "waiting for the players' answer" in str(fake.requests[0].messages)


def test_m31_keepsake_handover_told() -> None:
    """V19 quests 699-700: the model gave the Sealed Creditor's Note while its prose had the
    broker "let the offer hang". An omission is not flagged (a whole-narration check the
    per-sentence guard cannot make safely, docs/DECISIONS.md); the fact line says the note is in
    Brienne's hands and a model-only note asks for the hand-over to be told."""
    turn = told_turn("m31-r4-quests", 700)
    line = _lines(turn, KeepsakeGained)
    assert "Sealed Creditor's Note: it is in Brienne's hands now" in line
    notes = event_notes(turn.state, list(turn.events))
    assert "Tell the Sealed Creditor's Note reaching Brienne in this narration." in notes
