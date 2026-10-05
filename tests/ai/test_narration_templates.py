"""Template narration (M4.5, SPEC 6.8, 13): deterministic prose from engine events, never empty."""

import re
from pathlib import Path
from typing import Any

from aidm.dm.fake_llm import fake_text
from aidm.dm.guard_flow import NarrationSource
from aidm.dm.llm_types import LlmMode
from aidm.dm.narration_templates import QUIET_LINE, template_narration
from aidm.dm.narrator import narrate
from aidm.models.events import AnyEvent, CreatureDied, HpChanged
from aidm.models.world import FeatureKind, Quest, QuestState, WorldFeature
from aidm.models.world_events import (
    FeatureDiscovered,
    FeatureIntroduced,
    PartyMoved,
    QuestUpdated,
)
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import party_state, run_tool

FAIL: dict[str, Any] = {
    "actor": "fighter",
    "ability_or_skill": "athletics",
    "dc_tier": "nearly_impossible",
    "reason": "climb",
}


def _failed_check() -> list[AnyEvent]:
    events = list(run_tool(party_state(), "request_check", **FAIL).events)
    assert any(getattr(getattr(e, "result", None), "success", True) is False for e in events)
    return events


async def test_v1_failed_checks_always_narrate(tmp_path: Path) -> None:
    events = _failed_check()
    disabled, _ = fake_client(tmp_path)
    disabled.mode = LlmMode.DISABLED
    empty, _ = fake_client(tmp_path, [fake_text("")])
    for client in (disabled, empty):
        stream = narrate(party_state(), events, client)
        text = await stream.collect()
        assert text.strip()
        assert "Fighter" in text and "Athletics attempt fails" in text
        assert stream.source is NarrationSource.TEMPLATE


def test_template_has_no_mechanics_numbers() -> None:
    state = party_state()
    events = [*_failed_check(), HpChanged(creature_id="fighter", delta=-4, new_hp=8)]
    lines = template_narration(events, state)
    assert lines and not any(re.search(r"\d", line) for line in lines)
    assert "Fighter is wounded." in lines


def test_template_covers_discovery_movement_death_and_quests() -> None:
    state = party_state()
    feature = WorldFeature(
        id="feat-hatch",
        kind=FeatureKind.DOOR,
        name="a hidden hatch",
        node_id="town",
        hidden=True,
        discover_dc=10,
    )
    apply(state, FeatureIntroduced(feature=feature))
    events: list[AnyEvent] = [
        FeatureIntroduced(feature=feature),
        FeatureDiscovered(feature_id="feat-hatch", creature_id="rogue"),
        PartyMoved(from_node="town", to_node="forest", scene_index=1),
        CreatureDied(creature_id="wizard"),
        QuestUpdated(quest=Quest(id="q1", title="The Lost Bell", state=QuestState.COMPLETED)),
    ]
    lines = template_narration(events, state)
    assert lines == [
        "Rogue discovers a hidden hatch.",
        "You travel on to Forest.",
        "Wizard falls and does not rise again.",
        "You have seen The Lost Bell through to the end.",
    ]


def test_template_never_empty_and_deduplicates() -> None:
    state = party_state()
    assert template_narration([], state) == [QUIET_LINE]
    assert template_narration([], state, "Nothing happens yet.") == ["Nothing happens yet."]
    twice = [HpChanged(creature_id="rogue", delta=-1, new_hp=3)] * 2
    assert template_narration(twice, state) == ["Rogue is wounded."]
