"""Helpers for the M23.4 quest offer tests: settle after a batch, travel, win the offered fight,
resolve region 1 of the sample campaign, accept the giver's ask."""

from aidm.models.campaign_state import OfferChoice
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
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
