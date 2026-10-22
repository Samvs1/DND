"""M27.11 review fix 4: forcing a lock is noisy, success or failure, and the engine says so once
per place ("The noise carries. Anything nearby is warned."), like the M27.5 light warning."""

from aidm.dm.event_text import event_lines
from aidm.dm.item_text import NOISE_WARNING
from aidm.dm.tool_context import ToolContext
from aidm.models.events import CheckResolved
from aidm.models.item_events import PlaceAlerted
from aidm.models.state import GameState
from aidm.models.world_events import FeatureIntroduced
from tests.ai.tool_fixtures import apply_result, run_tool
from tests.unit.rules.item_fixtures import DOCKS, at, hero

HERO = ToolContext(actor_id="hero")


def _lock(state: GameState, name: str) -> str:
    result = run_tool(
        state, "introduce_feature", ctx=HERO, kind="container", name=name, lock_tier="easy"
    )
    apply_result(state, result)
    (event,) = result.events
    assert isinstance(event, FeatureIntroduced)
    return event.feature.id


def _force(state: GameState, feature: str, seed: int) -> list[str]:
    result = run_tool(
        state,
        "request_check",
        ctx=HERO,
        seed=seed,
        actor="hero",
        ability_or_skill="athletics",
        dc_tier="easy",
        feature=feature,
    )
    assert result.error is None, result.error
    apply_result(state, result)
    assert any(isinstance(e, CheckResolved) for e in result.events)
    return event_lines(state, result.events)


def test_forcing_a_lock_adds_the_noise_line_once_per_place() -> None:
    state = at(DOCKS, hero(gear=["crowbar"]))
    first = _force(state, _lock(state, "Iron chest"), seed=3)
    assert sum(NOISE_WARNING in line for line in first) == 1
    assert state.world.alerted == DOCKS and state.world.alerted_by == "noise"
    second = _force(state, _lock(state, "Second chest"), seed=5)  # same place: no second warning
    assert not any(NOISE_WARNING in line for line in second)


def test_noise_line_ignores_a_light_alert() -> None:
    state = at(DOCKS, hero())
    assert event_lines(state, [PlaceAlerted(node=DOCKS, reason="light")]) == []
