"""request_check with gear boons (M27.3): the engine applies a hero's boon whatever the AI asked,
names it in `adv_why`, and advantage never stacks with the AI's own advantage."""

from aidm.data.item_uses import item_use_data
from aidm.models.dice import AdvState
from aidm.models.events import CheckResolved
from aidm.models.state import GameState
from aidm.models.world import ActiveBoon
from aidm.models.world_events import PartyMoved
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import run_tool
from tests.sim.sim_setup import build_party

HERE = "quay"


def _with_glass() -> GameState:
    state = GameState(campaign_id="gear", seed=3)
    build_party(state, 1)
    apply(state, PartyMoved(from_node=None, to_node=HERE, scene_index=1))
    state.world.boons = [
        ActiveBoon(
            creature_id="rogue",
            use_id="magnifying-glass-inspect",
            name="Magnifying glass",
            skills=("investigation",),
            node=HERE,
        )
    ]
    return state


def _check(state: GameState, skill: str, advantage: str = "normal") -> CheckResolved:
    result = run_tool(
        state,
        "request_check",
        actor="rogue",
        ability_or_skill=skill,
        dc_tier="easy",
        advantage=advantage,
    )
    assert result.ok
    event = result.events[0]
    assert isinstance(event, CheckResolved)
    return event


def test_boon_applies_whatever_the_ai_asked() -> None:
    state = _with_glass()
    check = _check(state, "investigation")
    assert check.result.roll.adv is AdvState.ADVANTAGE
    assert check.result.adv_why == ("Magnifying glass",)
    assert _check(state, "athletics").result.roll.adv is AdvState.NORMAL


def test_boon_and_ai_advantage_do_not_stack() -> None:
    check = _check(_with_glass(), "investigation", "advantage")
    assert len(check.result.roll.rolls) == 2
    assert "Magnifying glass" in check.result.adv_why


def test_boon_cancels_the_ai_s_disadvantage() -> None:
    check = _check(_with_glass(), "investigation", "disadvantage")
    assert check.result.roll.adv is AdvState.NORMAL


def test_magnifying_glass_data_is_the_srd_inspect_advantage() -> None:
    # SRD 5.1 Adventuring Gear, Magnifying Glass: advantage on checks to inspect an item.
    glass = next(u for u in item_use_data().uses if u.id == "magnifying-glass-inspect")
    assert glass.effect.kind == "boon"
