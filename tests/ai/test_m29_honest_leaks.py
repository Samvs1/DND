"""M29.5c the honest storyteller: leaks and the epilogue (docs/playtests/M29_round1.md G22 G35
G36). Instructions to the storyteller never reach a player's line, placeholders never reach
prose, and the epilogue is built from (and checked against) the final state (FakeLLM only)."""

from pathlib import Path

from aidm.dm.epilogue import epilogue_checker, write_epilogue
from aidm.dm.epilogue_facts import epilogue_facts
from aidm.dm.fake_llm import fake_text
from aidm.dm.guard import prose_checker
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.guard_leaks import instruction_free
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narrator import narrate
from aidm.models.campaign_events import FinaleChosen, RegionResolved
from aidm.models.state import GameState
from aidm.session.public_feed import public_line
from tests.ai.epilogue_fixtures import finished_campaign, turned_and_dead
from tests.ai.fake_scripts import fake_client
from tests.session.playtest_saves import told_turn
from tests.session.progression_fixtures import apply_all, plan

LEAK = "Do NOT choose for them and do not tell either ending: end with that question."


def _kinds(state: GameState, text: str) -> set[ViolationKind]:
    return {v.kind for v in prose_checker(state)(text).violations}


def test_m29_finale_notice_lines_carry_no_instruction() -> None:
    """G36 (p3 1551, 1760): the finale question and the chosen ending were shown to players with
    "Do NOT choose for them..." and "Tell this ending as it happens now" in them."""
    _, state, log, _ = finished_campaign(ending=None)
    final = next(e for e in reversed(log) if isinstance(e, RegionResolved))
    asked = public_line(state, final) or ""
    assert "must now choose" in asked
    assert "NOT" not in asked and "do not" not in asked.lower() and "end with" not in asked
    chosen = FinaleChosen(option_id="silence-the-song")
    apply_all(state, [chosen], log)
    told = public_line(state, chosen) or ""
    assert "Silence the song" in told and "Tell this ending" not in told


def test_m29_instruction_text_is_cut_and_flagged(tmp_path: Path) -> None:
    """G36: the ONE filter cuts storyteller instructions from any public line, and THE guard
    flags them in model prose."""
    line = f"The last region is resolved. {LEAK}"
    assert instruction_free(line) == "The last region is resolved."
    assert instruction_free("A plain line.") == "A plain line."
    _, state, _, _ = finished_campaign()
    assert ViolationKind.INSTRUCTION_LEAK in _kinds(state, LEAK)
    assert ViolationKind.INSTRUCTION_LEAK in _kinds(state, "Tell this ending as it happens now.")
    assert not _kinds(state, "The beacon gutters, and the choir falls silent.")


async def test_m29_placeholder_never_reaches_prose(tmp_path: Path) -> None:
    """G22 (p2 142): the retry scrubbed the Cold Ledger to "[unlisted]" and the model copied the
    token into prose. The token is flagged, and a keepsake's own name is known (no scrub)."""
    turn = told_turn("p2", 142)
    check = prose_checker(turn.state, turn.events)
    assert ViolationKind.PLACEHOLDER in {v.kind for v in check(turn.prose).violations}
    assert check("Rook slips the Cold Ledger away among his gear.").ok
    client, _ = fake_client(tmp_path, [fake_text(turn.prose), fake_text(turn.prose)])
    stream = narrate(turn.state, list(turn.events), client)
    text = await stream.collect()
    assert text and "[unlisted]" not in text and stream.source is NarrationSource.TEMPLATE


async def test_m29_epilogue_facts_follow_the_final_state(tmp_path: Path) -> None:
    """G35 (p3 1761): the epilogue said the living Matron "fell" and the slain Varek "kept his
    word" because the facts said both had joined the party."""
    state = turned_and_dead()
    first, last = plan().acts[0].region.boss.name, plan().acts[2].region.boss.name
    lines = epilogue_facts(state).lines()
    assert f"At the end, {first} is dead." in lines and f"At the end, {last} is alive." in lines
    told = " ".join(lines)
    assert "but later died in a fight" in told and "turned on the party" in told
    check = epilogue_checker(state)
    assert ViolationKind.LIVING_DECLARED_DEAD in {
        v.kind for v in check(f"{last} herself fell, and her court with her.").violations
    }
    assert ViolationKind.DEAD_ACTING in {
        v.kind for v in check(f"In the end {first} kept his word to the vale.").violations
    }
    bad = f"{last} fell at the last. {first} kept his word."
    client, _ = fake_client(tmp_path, [fake_text(bad), fake_text(bad)])
    result = await write_epilogue(state, client)
    assert result is not None and result.source is NarrationSource.TEMPLATE
    assert "still lives" in result.text and "kept his word" not in result.text
