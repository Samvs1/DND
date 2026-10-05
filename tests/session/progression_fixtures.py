"""Fixtures for the progression tests: the sample campaign installed for a level-1 party."""

import random

from aidm.dm.arrival import offer_data
from aidm.dm.campaign_sample import load_sample_campaign
from aidm.dm.tool_context import ToolContext, tool_registries
from aidm.dm.tool_exec import execute_tool
from aidm.models.abilities import Skill
from aidm.models.campaign import CampaignPlan
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import AnyEvent, CreatureDied
from aidm.models.state import GameState
from aidm.models.world_events import PartyMoved
from aidm.rules.campaign_install import install_campaign
from aidm.rules.dice import Rng
from aidm.rules.encounter import encounter_outcome, end_encounter
from aidm.rules.encounter_offer import OfferData, arrival_offer_events
from aidm.rules.offer_answer import answer_offer
from aidm.rules.progression import region_resolution_events
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import tool_call
from tests.sim.sim_setup import build_party

REGS = tool_registries()
DATA: OfferData = offer_data(REGS)
SEED = 11


class Rigged:
    """An Rng that always rolls its highest (or lowest) value."""

    def __init__(self, high: bool) -> None:
        self.high = high

    def randint(self, a: int, b: int, /) -> int:
        return b if self.high else a


def plan() -> CampaignPlan:
    return load_sample_campaign()


def campaign_state(level: int = 1) -> tuple[GameState, GameState, list[AnyEvent]]:
    """(the state before install, the live state, the log applied since)."""
    state = GameState(campaign_id="prog", seed=SEED)
    build_party(state, level)
    start = state.model_copy(deep=True)
    log = apply_all(state, install_campaign(state, plan(), SEED))
    return start, state, log


def apply_all(
    state: GameState, events: list[AnyEvent], log: list[AnyEvent] | None = None
) -> list[AnyEvent]:
    for event in events:
        apply(state, event)
    if log is not None:
        log.extend(events)
    return list(events)


def move(state: GameState, node: str, log: list[AnyEvent]) -> list[AnyEvent]:
    """move_party through the DM tool, then the world's arrival (offer) events."""
    result = execute_tool(
        state, tool_call("move_party", node_id=node), ToolContext("fighter"), random.Random(1), REGS
    )
    assert result.ok, result.error
    apply_all(state, list(result.events), log)
    moved = result.events[0]
    assert isinstance(moved, PartyMoved)
    return apply_all(state, arrival_offer_events(state, DATA, moved.from_node), log)


def pending(state: GameState) -> EncounterOffer:
    assert state.campaign is not None and state.campaign.offer is not None
    return state.campaign.offer


def answer(
    state: GameState,
    choice: OfferChoice,
    log: list[AnyEvent],
    rng: Rng | None = None,
    skill: Skill | None = None,
) -> list[AnyEvent]:
    used = rng if rng is not None else random.Random(3)
    events = answer_offer(state, choice, DATA, used, actor_id="fighter", skill=skill)
    return apply_all(state, events, log)


def win_fight(state: GameState, log: list[AnyEvent]) -> None:
    """Force a victory: every hostile combatant dies, then the fight ends and regions resolve."""
    enc = state.encounter
    assert enc is not None and enc.status is EncounterStatus.ACTIVE
    for cid, combatant in sorted(enc.combatants.items()):
        if combatant.side is Side.HOSTILE:
            apply_all(state, [CreatureDied(creature_id=cid)], log)
    assert encounter_outcome(state) is EncounterStatus.VICTORY
    apply_all(state, end_encounter(state, EncounterStatus.VICTORY), log)
    apply_all(state, region_resolution_events(state), log)
