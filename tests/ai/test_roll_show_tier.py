"""M26.2: DM-requested checks and saves carry their DC tier, so the dice show can say it."""

from aidm.models.checks import DcTier
from aidm.models.events import CheckResolved
from aidm.rules.d20 import SITUATION
from aidm.session.dice_view import dice_view
from tests.ai.tool_fixtures import party_state, run_tool


def test_request_check_carries_the_tier_word_and_the_situation() -> None:
    state = party_state()
    state.world.region_tier = 3  # M29.6b: very hard is allowed from act 3 on
    result = run_tool(
        state,
        "request_check",
        actor="rogue",
        ability_or_skill="stealth",
        dc_tier="very_hard",
        advantage="advantage",
    )
    event = result.events[0]
    assert isinstance(event, CheckResolved) and event.result.tier is DcTier.VERY_HARD
    view = dice_view(event)
    assert view is not None and view.difficulty == "very hard"
    assert view.adv_why == (SITUATION,) and view.source_id is None


def test_request_save_carries_the_tier() -> None:
    state = party_state()
    result = run_tool(state, "request_save", actors=["rogue"], ability="dex", dc_tier="easy")
    event = result.events[0]
    assert isinstance(event, CheckResolved) and event.result.tier is DcTier.EASY
    view = dice_view(event)
    assert view is not None and view.difficulty == "easy" and view.kind.value == "save"
