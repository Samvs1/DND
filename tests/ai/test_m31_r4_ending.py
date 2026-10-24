"""M31.1c V20 (docs/playtests/M31_round4.md, full 1643): the ending told the Grieving Spark "won
over" and also "laid low", listed no quests and closed on a template filler ("the scene waits on
your next move"). The quest list and who lived are now engine-written lines after the prose, an
ally told defeated is flagged, and an ending has no filler (FakeLLM only, never the network)."""

from pathlib import Path

from aidm.dm.epilogue import epilogue_checker, honest_facts, write_epilogue
from aidm.dm.epilogue_facts import epilogue_facts, epilogue_record
from aidm.dm.fake_llm import fake_text
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narration_templates import CLOSING_LINE
from aidm.models.campaign_events import EpilogueWritten
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import logged, replay_until

K = ViolationKind
_END = 1643
HONEST = (
    "The Moonwell of Ash ended not in fire, but in a slow green return. "
    "In The Rotwood Verge, Brother Mallow was defeated by force after cunning paved the way. "
    "The Weeping Keeper sided with the party and lived on, and so did The Grieving Spark, won"
    " over after the Prayer-Knot was found."
)


def _real() -> str:
    event = logged("m31-r4-full", _END).event
    assert isinstance(event, EpilogueWritten)
    return event.text


def test_m31_ally_told_defeated_is_flagged() -> None:
    state = replay_until("m31-r4-full", _END)
    check = epilogue_checker(state)
    found = {(v.kind, v.span) for v in check(_real()).violations}
    assert (K.ALLY_DEFEATED, "the Grieving Spark") in found, found
    assert not check(HONEST).violations


def test_m31_finale_question_that_lays_an_ally_low_is_left_out() -> None:
    state = replay_until("m31-r4-full", _END)
    assert "laid low" in "\n".join(epilogue_facts(state).lines())
    facts = honest_facts(state)
    told = "\n".join(facts.lines())
    assert "laid low" not in told and "The party chose: The Kept Sorrow." in told


def test_m31_ending_record_is_engine_written() -> None:
    record = epilogue_record(honest_facts(replay_until("m31-r4-full", _END)))
    assert record[0] == "Brienne, Elowen, Rook, Tamsin lived on."
    assert record[1].startswith("Main quests: The Grey Borderlands (completed),")
    assert "Completed quests: Ledger of the Empty Houses, The Root-ferryman's Debt." in record
    assert "Left behind: The Pale Toll." in record


async def test_m31_ending_mixed_has_no_filler_and_keeps_the_record(tmp_path: Path) -> None:
    """The real epilogue: its first sentences pass, the 'laid low' one is flagged twice, so the
    ending is mixed; it closes on the engine's record, never on 'the scene waits'."""
    state = replay_until("m31-r4-full", _END)
    real = _real().replace(CLOSING_LINE, "").strip()
    client, _ = fake_client(tmp_path, [fake_text(real), fake_text(real)])
    result = await write_epilogue(state, client)
    assert result is not None and result.source is NarrationSource.MIXED
    assert "waits on your next move" not in result.text and "laid low" not in result.text
    record = epilogue_record(honest_facts(state))
    assert result.text.endswith(" ".join(record))


async def test_m31_ending_model_prose_then_record(tmp_path: Path) -> None:
    state = replay_until("m31-r4-full", _END)
    client, _ = fake_client(tmp_path, [fake_text(HONEST)])
    result = await write_epilogue(state, client)
    assert result is not None and result.source is NarrationSource.MODEL
    record = " ".join(epilogue_record(honest_facts(state)))
    assert result.text == f"{HONEST} {record}"
