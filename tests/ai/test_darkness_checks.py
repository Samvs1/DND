"""request_check in a dark place (M27.2): the engine adds Darkness, never hides a quest item."""

from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.dice import AdvState
from aidm.models.events import CheckResolved
from aidm.models.state import GameState
from aidm.models.world import WorldItem
from aidm.models.world_events import ItemDiscovered, ItemPlaced, PartyMoved, PlaceLit
from aidm.rules.campaign_install import install_campaign
from aidm.rules.light import DARKNESS
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import run_tool
from tests.sim.sim_setup import build_party

CAVE = "saltcellar-tunnels"  # sample campaign: cave, crypt


def _cave() -> GameState:
    state = GameState(campaign_id="dark", seed=3)
    build_party(state, 1)
    for event in install_campaign(state, load_sample_campaign(), 3):
        apply(state, event)
    apply(state, PartyMoved(from_node=state.world.current_node, to_node=CAVE, scene_index=1))
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


def test_search_in_a_dark_place_is_at_disadvantage_whatever_the_ai_asked() -> None:
    state = _cave()
    dark = _check(state, "perception")
    assert dark.result.roll.adv is AdvState.DISADVANTAGE
    assert dark.result.adv_why == (DARKNESS,)
    assert _check(state, "athletics").result.roll.adv is AdvState.NORMAL
    cancelled = _check(state, "investigation", "advantage")
    assert cancelled.result.roll.adv is AdvState.NORMAL  # SRD: never stacks, they cancel


def test_a_lit_cave_searches_normally() -> None:
    state = _cave()
    apply(state, PlaceLit(node=CAVE, by="rogue"))
    assert _check(state, "perception").result.roll.adv is AdvState.NORMAL


def test_darkness_never_hides_a_quest_item() -> None:
    # GOAL_ITEMS "Never a softlock": darkness only adds disadvantage; the DC stays the same.
    state = _cave()
    item = WorldItem(
        id="it-ledger", name="ledger", node_id=CAVE, hidden=True, discover_dc=10, quest_id="q1"
    )
    apply(state, ItemPlaced(item=item))
    found = False
    for seed in range(1, 41):
        result = run_tool(
            state,
            "request_check",
            seed=seed,
            actor="rogue",
            ability_or_skill="perception",
            dc_tier="easy",
        )
        check = result.events[0]
        assert isinstance(check, CheckResolved) and check.result.adv_why == (DARKNESS,)
        if any(isinstance(e, ItemDiscovered) for e in result.events):
            assert check.result.roll.total >= 10
            found = True
            break
    assert found
