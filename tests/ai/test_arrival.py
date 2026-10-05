"""M5.4 arrival: lazy node descriptions (generated once, guarded, fallback) and the offer hook."""

from pathlib import Path

from aidm.dm.arrival import describe_place, fallback_place_description, on_arrival
from aidm.dm.event_text import event_lines
from aidm.dm.fake_llm import FakeLLM, FakeStream
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_log import LlmCallLog
from aidm.dm.llm_settings import LlmSettings
from aidm.dm.llm_types import LlmMode, LlmRole
from aidm.dm.narration_templates import template_narration
from aidm.models.campaign_events import EncounterOffered
from aidm.models.world_events import NodeDescribed
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import run_tool
from tests.session.progression_fixtures import REGS, campaign_state, plan

GOOD = FakeStream(
    ("Salt wind drags across the warped planks of the quay. ", "Gulls wheel above grey water. ")
)
INVENTED = FakeStream(("Sister Kelene waits by the pier with her hounds. ",))


def _disabled(tmp_path: Path) -> LlmClient:
    settings = LlmSettings(api_key=None, log_path=tmp_path / "llm.jsonl")
    return LlmClient(FakeLLM(), settings, LlmMode.DISABLED, LlmCallLog(settings.log_path))


async def test_description_is_generated_once_and_reused(tmp_path: Path) -> None:
    _, state, _ = campaign_state()
    client, fake = fake_client(tmp_path, [GOOD])
    events = await describe_place(state, client)
    assert len(events) == 1 and isinstance(events[0], NodeDescribed)
    assert events[0].text.startswith("Salt wind drags")
    assert events[0].node_id == plan().acts[0].region.arrival.id
    assert fake.requests[0].model == client.model_for(LlmRole.FAST)
    apply(state, events[0])
    assert await describe_place(state, client) == []
    assert len(fake.requests) == 1


async def test_no_key_uses_the_plan_flavour(tmp_path: Path) -> None:
    _, state, _ = campaign_state()
    events = await describe_place(state, _disabled(tmp_path))
    arrival = plan().acts[0].region.arrival
    assert isinstance(events[0], NodeDescribed)
    assert events[0].text == fallback_place_description(state, arrival.id)
    assert arrival.flavour.rstrip(".") in events[0].text


async def test_guard_rejected_description_falls_back(tmp_path: Path) -> None:
    _, state, _ = campaign_state()
    client, _ = fake_client(tmp_path, [INVENTED, INVENTED])
    events = await describe_place(state, client)
    assert isinstance(events[0], NodeDescribed)
    assert "Kelene" not in events[0].text
    assert events[0].text == fallback_place_description(state, events[0].node_id)


async def test_on_arrival_describes_then_offers(tmp_path: Path) -> None:
    _, state, _ = campaign_state()
    region = plan().acts[0].region
    moved = run_tool(state, "move_party", node_id=region.spokes[0].id)
    for event in moved.events:
        apply(state, event)
    events = await on_arrival(
        state,
        _disabled(tmp_path),
        REGS,
        retreat_node=region.arrival.id,
        apply=lambda e: apply(state, e),
    )
    assert [type(e) for e in events] == [NodeDescribed, EncounterOffered]
    assert state.world.descriptions[region.spokes[0].id]
    assert state.campaign is not None and state.campaign.offer is not None


async def test_offer_is_a_warning_beat_in_templates_and_context(tmp_path: Path) -> None:
    _, state, _ = campaign_state()
    region = plan().acts[0].region
    for event in run_tool(state, "move_party", node_id=region.spokes[0].id).events:
        apply(state, event)
    events = await on_arrival(
        state, _disabled(tmp_path), REGS, retreat_node=None, apply=lambda e: apply(state, e)
    )
    story = template_narration(events[1:], state)
    assert "Fight, strike first, slip away, or try to talk?" in story[0]
    assert not any(ch.isdigit() for line in story for ch in line)
    fact = event_lines(state, events[1:])[0]
    assert fact.startswith("WARNING BEAT") and "Nothing has started yet" in fact
