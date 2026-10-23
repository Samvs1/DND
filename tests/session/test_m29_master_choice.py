"""M29.7c the master's choice (docs/playtests/M29_round2.md R14, R15): a finished Peace route
never answers the master's encounter offer; the party answers, and a parley then surely holds.
A confirmed attack on an allied master starts the fight. Each case starts from its live save
(tests/session/playtest_saves.py)."""

import random

import pytest

from aidm.dm.arrival import offer_data
from aidm.dm.quest_text import PEACE_WAITS, QUEST_EVENT_LINES
from aidm.dm.tool_context import ToolContext, ToolResult, tool_registries
from aidm.dm.tool_exec import execute_tool
from aidm.models.campaign_events import OfferResolved, RegionResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.quest_events import QuestStepDone
from aidm.models.state import GameState
from aidm.models.world_events import AttitudeChanged
from aidm.rules.finale import FinaleRefused, choose_events, finale_open
from aidm.rules.offer_answer import answer_offer, sure_parley
from aidm.rules.quest_progress import quest_progress_events
from aidm.rules.quest_rewards import resolution_reward_events
from aidm.session.reducer import apply
from aidm.session.views import public_offer
from aidm.session.views_quests import public_finale
from tests.ai.tool_fixtures import tool_call
from tests.session.playtest_saves import replay_until

REGS = tool_registries()


def _settle(state: GameState) -> list[AnyEvent]:
    """The session's quest passes (`quest_flow.settle_after`, without the people part)."""
    out: list[AnyEvent] = []
    for _ in range(8):
        moved = quest_progress_events(state, REGS.tiers, REGS.catalogue)
        moved += resolution_reward_events(state, REGS.tiers, REGS.catalogue)
        if not moved:
            break
        for event in moved:
            apply(state, event)
        out += moved
    return out


def _waiting(run: str, seq: int, boss: str) -> GameState:
    state = replay_until(run, seq)
    events = _settle(state)
    assert any(isinstance(e, QuestStepDone) for e in events)  # the route's last step is met
    assert not any(isinstance(e, RegionResolved | OfferResolved) for e in events)
    assert state.campaign is not None and state.campaign.offer is not None
    assert state.campaign.offer.boss_npc_id == boss
    return state


def test_m29_peace_route_waits_for_the_players_answer_p4_final_master() -> None:
    """p4 1724-1733: arriving at the Saltwright's Forge met the last step ("Stand before the
    Saltwright ...") and the offer resolved as a parley nobody chose (+2600 XP, finale)."""
    state = _waiting("r2-p4", 1725, "boss-the-brineheart-deeps")
    offer = state.campaign.offer if state.campaign is not None else None
    assert offer is not None and sure_parley(state, offer)
    view = public_offer(state)
    assert view is not None and view.sure == (OfferChoice.PARLEY,)
    data = offer_data(REGS)
    events = answer_offer(state, OfferChoice.PARLEY, data, random.Random(1), actor_id="pc-p2")
    assert not any(isinstance(e, CheckResolved) for e in events)  # sure: no roll
    assert isinstance(events[0], OfferResolved) and events[0].success
    for event in events:
        apply(state, event)
    after = _settle(state)
    resolved = [e for e in after if isinstance(e, RegionResolved)]
    assert [(e.region_id, e.how.value) for e in resolved] == [("the-brineheart-deeps", "alliance")]


def test_m29_peace_route_leaves_the_fight_open() -> None:
    """The party may still fight the master it could win over: its answer decides."""
    state = _waiting("r2-p4", 1725, "boss-the-brineheart-deeps")
    data = offer_data(REGS)
    events = answer_offer(state, OfferChoice.FIGHT, data, random.Random(1), actor_id="pc-p2")
    assert any(isinstance(e, EncounterStarted) for e in events)


def test_m29_peace_route_waits_for_the_act_one_master_p7_gurn() -> None:
    """p7 323-330: the same pattern with the first master (Gurn the Tollkeeper)."""
    state = _waiting("r2-p7", 324, "boss-brambleheath-fens")
    offer = state.campaign.offer if state.campaign is not None else None
    assert offer is not None and sure_parley(state, offer)


def test_m29_waiting_master_is_told_to_the_storyteller() -> None:
    state = replay_until("r2-p4", 1725)
    done = [e for e in _settle(state) if isinstance(e, QuestStepDone)]
    line = QUEST_EVENT_LINES[QuestStepDone](state, done[-1])
    assert line is not None and PEACE_WAITS in line
    assert "the party stands with The Saltwright" in line


def _attack(state: GameState, confirm: bool) -> ToolResult:
    call = tool_call(
        "creative_effect",
        actor="pc-p2",
        target="boss-the-brineheart-deeps",
        effect_kind="minor_damage",
        severity="major",
    )
    return execute_tool(state, call, ToolContext("pc-p2", confirm), random.Random(1), REGS)


def test_m29_confirmed_attack_on_an_allied_master_starts_the_fight_p4() -> None:
    """p4 1741-1747: with the Saltwright an ally and the finale up, "drive my dagger into its
    back" was confirmed past the point of no return; it turned hostile, no fight started and the
    narration had it dodge. Now the confirmed attack starts the fight, and the ending waits."""
    state = replay_until("r2-p4", 1742)
    assert finale_open(state) is not None
    asked = _attack(state, confirm=False)
    assert asked.pending is not None
    result = _attack(state, confirm=True)
    assert result.ok, result.error
    started = [e for e in result.events if isinstance(e, EncounterStarted)]
    assert started and any(isinstance(e, AttitudeChanged) and e.hostile for e in result.events)
    for event in result.events:
        apply(state, event)
    saltwright = [c for c in state.creatures.values() if c.name == "The Saltwright"]
    assert saltwright and not saltwright[0].dead
    assert public_finale(state) is None  # the fight comes first
    with pytest.raises(FinaleRefused):
        choose_events(state, "the-open-road")
