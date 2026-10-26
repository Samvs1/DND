"""Story records are past records on the round-7 saves (M40.4, docs/playtests/M39_round7.md).

The narrator prompt is rebuilt from the saves as `narrate` builds it (the audit's
`build_prompt`): a stale fact is left out, the rest is dated, and the sections say that only
the engine's lines are the present. The r7b-typed lie ("her offers ... were not taken up", no
engine event refused anything) is not written as a fact any more.
"""

from pathlib import Path

from aidm.dm.context import MEMORY_TITLE, PAST_NOTES_TITLE
from aidm.dm.epilogue_facts import epilogue_facts
from aidm.dm.fake_llm import fake_tool_call
from aidm.dm.memory import summarise
from aidm.dm.tool_context import ToolContext
from aidm.models.world_events import FactRecorded
from aidm.rules.story_claims import ClaimKind, unsupported_claims
from aidm.session.views import public_facts
from scripts.audit.replay import build_prompt
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import run_tool
from tests.session.playtest_saves import events_of, replay_until, told_turn

STIRGES = "no blow has yet been struck"
ROSE = "Two stirges rose"  # fact-8 at seq 197 (r7b-full)
NOT_YET = "has not yet accepted or refused"
LIE = (
    "Brienne gave Rook two torches; her offers of three gold to Elowen and Rook and of a"
    " blanket to Rook were not taken up."
)
HEROES = ["pc-p2", "pc-p4", "pc-p6"]


def _prompt(run: str, seq: int) -> str:
    told = told_turn(run, seq)
    return build_prompt(told.state, told.events, told.actor_id, told.player_text)


def test_r7_full_513_the_hovering_stirges_fact_is_left_out() -> None:
    told = told_turn("m39-r7-full", 513)
    fact = next(f for f in told.state.world.facts if ROSE in f.text)  # still in the ledger
    assert fact.made is not None and fact.made.seq == 197  # an old save stamped on replay
    prompt = _prompt("m39-r7-full", 513)
    assert STIRGES not in prompt
    assert PAST_NOTES_TITLE in prompt and MEMORY_TITLE in prompt


def test_r7_quests_119_the_not_yet_accepted_fact_is_left_out() -> None:
    prompt = _prompt("m39-r7-quests", 119)
    assert NOT_YET not in prompt
    assert "Earlier" in prompt.split(PAST_NOTES_TITLE, 1)[1].split("##", 1)[0]


def test_r7_journal_and_epilogue_leave_the_stale_facts_out() -> None:
    log = events_of("m39-r7-full")
    state = replay_until("m39-r7-full", log[-1].seq + 1)
    assert any(ROSE in f.text for f in state.world.facts)
    assert not any(ROSE in f for f in public_facts(state))
    assert not any(ROSE in f for f in epilogue_facts(state).ledger)


def test_r7_typed_the_refused_offers_lie_has_no_engine_event() -> None:
    state = replay_until("m39-r7-typed", 59)  # the summary of the wharf scene comes next
    assert unsupported_claims(state, LIE, HEROES) == (ClaimKind.REFUSAL,)
    assert unsupported_claims(state, "Brienne gave Rook two torches.", HEROES) == ()


async def test_r7_typed_the_summariser_drops_the_lie(tmp_path: Path) -> None:
    state = replay_until("m39-r7-typed", 59)
    draft = {
        "title": "Gear on the wharf",
        "summary": "Brienne handed Rook two torches on the wharf.",
        "entity_ids": ["pc-p2", "pc-p6"],
        "facts": [
            {"text": LIE, "entity_ids": HEROES, "tags": ["gear"]},
            {"text": "Brienne gave Rook two torches.", "entity_ids": HEROES, "tags": ["gear"]},
        ],
    }
    client, _ = fake_client(tmp_path, [fake_tool_call("submit_result", draft)])
    outcome = await summarise(state, client)
    facts = [e.fact.text for e in outcome.events if isinstance(e, FactRecorded)]
    assert facts == ["Brienne gave Rook two torches."], outcome.dropped
    assert any("refusal no event made" in d for d in outcome.dropped)


def test_r7_typed_the_note_tool_refuses_the_lie() -> None:
    state = replay_until("m39-r7-typed", 59)
    ctx = ToolContext(actor_id="pc-p2")
    refused = run_tool(state, "record_fact", ctx=ctx, text=LIE, entity_ids=HEROES, tags=[])
    assert refused.error is not None and "refusal" in refused.error
    kept = run_tool(
        state, "record_fact", ctx=ctx, text="Brienne gave Rook two torches.", entity_ids=HEROES
    )
    assert kept.ok
