"""Narrator over FakeLLM (M4.5, SPEC 6.1 step 3, 6.8, 11): streaming, tone, fallbacks."""

from pathlib import Path
from typing import Any

from aidm.dm.adjudicator import AdjudicationResult, ResolvedCall
from aidm.dm.fake_llm import FakeHang, FakeRaise, FakeStream, fake_text
from aidm.dm.llm_backend import BackendError, BackendTimeout
from aidm.dm.llm_types import FailureReason
from aidm.dm.narration_stream import NarrationSource, NarrationTone
from aidm.dm.narration_templates import CLOSING_LINE
from aidm.dm.narrator import (
    NARRATION_STYLE,
    NUMBERS_ALLOWED,
    narrate,
    narrate_round_segment,
    record_narration,
    tone_for,
)
from aidm.models.events import AnyEvent
from aidm.models.world_events import AttitudeChanged
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import add_npc, party_state, run_tool, tool_call

CHECK: dict[str, Any] = {
    "actor": "fighter",
    "ability_or_skill": "athletics",
    "dc_tier": "easy",
    "reason": "climb",
}


def _check_events(dc_tier: str = "easy") -> list[AnyEvent]:
    state = party_state()
    args: dict[str, Any] = {**CHECK, "dc_tier": dc_tier}
    return list(run_tool(state, "request_check", **args).events)


async def test_streams_complete_sentences_in_order(tmp_path: Path) -> None:
    pieces = ("You climb", " the wall. Mr. Ash", " watches... then claps", '. "Bravo!" ', "Done")
    client, fake = fake_client(tmp_path, [FakeStream(pieces)])
    stream = narrate(party_state(), _check_events(), client)
    texts = [c.text for c in [chunk async for chunk in stream]]
    assert texts == [
        "You climb the wall.",
        "Mr. Ash watches... then claps.",
        '"Bravo!"',
        "Done",
    ]
    assert [c.index for c in stream.chunks] == [0, 1, 2, 3]
    assert stream.source is NarrationSource.MODEL and stream.failure is None
    assert len(fake.requests) == 1 and fake.requests[0].model == "deepseek-v4-pro"


async def test_prompt_carries_style_facts_and_no_numbers_rule(tmp_path: Path) -> None:
    state = party_state()
    result = run_tool(state, "request_check", **CHECK)
    adjudication = AdjudicationResult(
        calls=(ResolvedCall(1, tool_call("request_check", **CHECK), result),),
        events=result.events,
    )
    client, fake = fake_client(tmp_path)
    await narrate(state, adjudication, client, actor_id="fighter", player_text="I climb").collect()
    body = "\n".join(str(m["content"]) for m in fake.requests[0].messages)
    assert NARRATION_STYLE in body and "no mechanics numbers" in body.lower()
    assert NUMBERS_ALLOWED not in body
    assert result.summary in body and "RESOLVED TOOL RESULTS" in body
    assert "<player_action" in body and "NPC PRIVATE" not in body
    await narrate(state, adjudication, client, allow_numbers=True).collect()
    assert NUMBERS_ALLOWED in str(fake.requests[1].messages[-1]["content"])


async def test_disabled_llm_uses_template(tmp_path: Path) -> None:
    client, fake = fake_client(tmp_path)
    client.mode = client.mode.DISABLED
    stream = narrate(party_state(), _check_events(), client)
    text = await stream.collect()
    assert stream.source is NarrationSource.TEMPLATE
    assert stream.failure is not None and stream.failure.reason is FailureReason.DISABLED
    assert "Fighter" in text and fake.requests == []


async def test_transport_failure_and_empty_answer_use_template(tmp_path: Path) -> None:
    for step in (FakeRaise(BackendError("http_500")), fake_text("   ")):
        client, _ = fake_client(tmp_path, [step])
        stream = narrate(party_state(), _check_events(), client)
        text = await stream.collect()
        assert stream.source is NarrationSource.TEMPLATE and text
        assert stream.failure is not None


async def test_timeout_falls_back_to_template(tmp_path: Path) -> None:
    client, _ = fake_client(tmp_path, [FakeHang(5.0)], timeout_s=0.05, idle_s=0.05)
    stream = narrate(party_state(), _check_events(), client)
    await stream.collect()
    assert stream.failure is not None and stream.failure.reason is FailureReason.TIMEOUT
    assert stream.source is NarrationSource.TEMPLATE and stream.chunks


async def test_partial_stream_then_timeout_appends_closing(tmp_path: Path) -> None:
    pieces = ("You haul yourself up. ", "The stones are slick. ", "Halfway up, the")
    client, _ = fake_client(tmp_path, [FakeStream(pieces, then=BackendTimeout())])
    stream = narrate(party_state(), _check_events(), client)
    texts = [c.text for c in [chunk async for chunk in stream]]
    assert texts == ["You haul yourself up.", "The stones are slick.", CLOSING_LINE]
    assert stream.source is NarrationSource.MIXED


async def test_short_partial_stream_appends_template_outcome(tmp_path: Path) -> None:
    events = _check_events("nearly_impossible")
    client, _ = fake_client(
        tmp_path, [FakeStream(("You reach up. ", "Then"), then=BackendTimeout())]
    )
    stream = narrate(party_state(), events, client)
    texts = [c.text for c in [chunk async for chunk in stream]]
    assert texts[0] == "You reach up." and len(texts) >= 2
    assert any("fails" in t for t in texts[1:])
    assert stream.source is NarrationSource.MIXED


async def test_tone_selection(tmp_path: Path) -> None:
    state = party_state()
    assert tone_for(state) is NarrationTone.EXPLORATION
    assert tone_for(state, social=True) is NarrationTone.SOCIAL
    npc = add_npc(state)
    social = [AttitudeChanged(npc_id=npc.id, social=5, deeds=0)]
    assert tone_for(state, social) is NarrationTone.SOCIAL
    fight = list(run_tool(state, "start_encounter", monster_ids=["goblin"], terrain_tags=[]).events)
    assert tone_for(state, fight) is NarrationTone.COMBAT
    for event in fight:
        apply(state, event)
    assert tone_for(state) is NarrationTone.COMBAT
    client, _ = fake_client(tmp_path)
    stream = narrate(state, [], client)
    assert {c.tone for c in [chunk async for chunk in stream]} == {NarrationTone.COMBAT}


async def test_batched_monster_turns_use_one_call(tmp_path: Path) -> None:
    state = party_state()
    events = list(
        run_tool(state, "start_encounter", monster_ids=["goblin"], terrain_tags=[]).events
    )
    for event in events:
        apply(state, event)
    turns = _check_events() * 3
    client, fake = fake_client(tmp_path, [fake_text("The goblins surge. Blades flash.")])
    stream = narrate_round_segment(state, turns, client)
    assert await stream.collect() == "The goblins surge. Blades flash."
    assert len(fake.requests) == 1 and stream.tone is NarrationTone.COMBAT
    assert "consecutive enemy turns" in str(fake.requests[0].messages[-1]["content"])


async def test_guard_hook_stops_flagged_sentence(tmp_path: Path) -> None:
    from aidm.dm.guard_types import GuardReport, Violation, ViolationKind

    def guard(text: str) -> GuardReport:
        bad = "Kelene" in text
        return GuardReport((Violation(ViolationKind.UNKNOWN_NAME, "Kelene", "x"),) if bad else ())

    client, _ = fake_client(tmp_path, [fake_text("Sister Kelene waves. You wave back.")])
    stream = narrate(party_state(), _check_events(), client, guard=guard)
    text = await stream.collect()
    assert "Kelene" not in text and text and stream.reports


def test_record_narration_event() -> None:
    state = party_state()
    assert record_narration(state, "  ") is None
    event = record_narration(state, " You rest. ")
    assert event is not None and event.text == "You rest." and event.scene_turn == 1
    apply(state, event)
    assert state.memory.narration[-1] == "You rest." and state.world.scene_turn == 1
