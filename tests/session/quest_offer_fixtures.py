"""Helpers for the M23.4 quest offer tests: settle after a batch, travel, win the offered fight,
resolve region 1 of the sample campaign, accept the giver's ask; the Slendee old save in act 2."""

import json
from pathlib import Path

from aidm.models.campaign import CampaignPlan
from aidm.models.campaign_events import RegionResolved
from aidm.models.campaign_state import OfferChoice, RegionResolution
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.models.world_events import PartyMoved, QuestUpdated
from aidm.rules.campaign_install import install_campaign
from aidm.rules.quest_offers import answer_events
from aidm.session.quest_flow import settle_after
from tests.session.progression_fixtures import (
    REGS,
    answer,
    apply_all,
    campaign_state,
    move,
    plan,
    win_fight,
)
from tests.sim.sim_setup import build_party

R1 = plan().acts[0].region
R2 = plan().acts[1].region


def settle(state: GameState, batch: list[AnyEvent], log: list[AnyEvent]) -> list[AnyEvent]:
    return settle_after(state, REGS, batch, lambda events: apply_all(state, events, log))


def go(state: GameState, node: str, log: list[AnyEvent]) -> list[AnyEvent]:
    mark = len(log)
    move(state, node, log)
    return settle(state, log[mark:], log)


def fresh() -> tuple[GameState, GameState, list[AnyEvent]]:
    """Installed (no quest offered) and the opening resolution settled."""
    start, state, log = campaign_state(offered=False)
    settle(state, list(log), log)
    return start, state, log


def accept(state: GameState, quest_id: str, log: list[AnyEvent]) -> list[AnyEvent]:
    events = apply_all(state, answer_events(state, quest_id, True), log)
    return [*events, *settle(state, events, log)]


def fight_won(state: GameState, log: list[AnyEvent]) -> None:
    mark = len(log)
    answer(state, OfferChoice.FIGHT, log)
    win_fight(state, log)
    settle(state, log[mark:], log)


def resolve_region_one(state: GameState, log: list[AnyEvent]) -> None:
    for spoke in R1.spokes:
        if state.world.current_node != R1.arrival.id:
            go(state, R1.arrival.id, log)
        go(state, spoke.id, log)
        if state.campaign is not None and state.campaign.offer is not None:
            fight_won(state, log)
    go(state, R1.gateway.id, log)
    fight_won(state, log)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "plan_weight_of_echoes.json"


def _moved(state: GameState, node: str) -> PartyMoved:
    world = state.world
    return PartyMoved(from_node=world.current_node, to_node=node, scene_index=world.scene_index + 1)


def slendee_in_act_two() -> tuple[GameState, GameState, list[AnyEvent], CampaignPlan]:
    """An old save: side quests bulk-offered without steps (pre-M23 events), act 1 resolved and
    the party at the act-2 arrival (the Slendee playtest)."""
    plan_ = CampaignPlan.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    state = GameState(campaign_id="slendee", seed=3)
    build_party(state, 3)
    start = state.model_copy(deep=True)
    log = apply_all(state, install_campaign(state, plan_, 3))
    old = [
        Quest(id=q.id, title=q.title, state=QuestState.OFFERED, giver_npc_id=q.giver_npc_id)
        for q in plan_.quests
        if q.act <= 2
    ]
    first, second = plan_.acts[0].region, plan_.acts[1].region
    resolved = RegionResolved(region_id=first.id, how=RegionResolution.DEFEAT, final=False)
    apply_all(state, [*(QuestUpdated(quest=q) for q in old), resolved], log)
    apply_all(state, [_moved(state, first.gateway.id), _moved(state, second.arrival.id)], log)
    return start, state, log, plan_
