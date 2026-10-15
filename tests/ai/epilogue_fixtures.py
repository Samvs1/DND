"""A finished sample campaign for the epilogue tests: three regions resolved by defeat, then the
finale chosen (M23.9; `ending=None` leaves the finale card open)."""

from __future__ import annotations

from aidm.models.campaign_events import FinaleChosen
from aidm.models.campaign_state import OfferChoice
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import AnyEvent, CreatureDied
from aidm.models.state import GameState
from aidm.models.world_events import FactRecorded
from aidm.rules.encounter import end_encounter
from aidm.rules.progression import campaign_complete, region_resolution_events
from tests.ai.tool_fixtures import run_tool
from tests.session.progression_fixtures import answer, apply_all, campaign_state, move, plan

FINAL_BOSS = plan().acts[2].region.boss.name
LEDGER_FACT = "The party found the smugglers' lantern code hidden in the cellar."
ENDING = "silence-the-song"


def kill_foes(state: GameState, log: list[AnyEvent]) -> list[AnyEvent]:
    """Every hostile combatant dies, the fight ends, regions resolve; returns the new events."""
    enc = state.encounter
    assert enc is not None
    out: list[AnyEvent] = []
    for cid, combatant in sorted(enc.combatants.items()):
        if combatant.side is Side.HOSTILE:
            out.extend(apply_all(state, [CreatureDied(creature_id=cid)], log))
    out.extend(apply_all(state, end_encounter(state, EncounterStatus.VICTORY), log))
    out.extend(apply_all(state, region_resolution_events(state), log))
    return out


def _tour(state: GameState, log: list[AnyEvent], act: int) -> list[AnyEvent]:
    region = plan().acts[act].region
    last: list[AnyEvent] = []
    for spoke in region.spokes:
        if state.world.current_node != region.arrival.id:
            move(state, region.arrival.id, log)
        move(state, spoke.id, log)
        answer(state, OfferChoice.FIGHT, log)
        kill_foes(state, log)
    move(state, region.gateway.id, log)
    answer(state, OfferChoice.FIGHT, log)
    last = kill_foes(state, log)
    return last


def finished_campaign(
    ending: str | None = ENDING, *, finale: bool = True
) -> tuple[GameState, GameState, list[AnyEvent], list[AnyEvent]]:
    """(start, finished state, full log, the events of the final boss fight). `finale=False`
    plays the sample plan without its finale (an old plan: it ends at the final resolution)."""
    bare = None if finale else plan().model_copy(update={"finale": None})
    start, state, log = campaign_state(plan_=bare)
    final: list[AnyEvent] = []
    for act in range(3):
        if act:
            move(state, plan().acts[act].region.arrival.id, log)
        final = _tour(state, log, act)
    ledger = run_tool(state, "record_fact", text=LEDGER_FACT, entity_ids=["tobin-marrow"], tags=[])
    apply_all(state, list(ledger.events), log)
    assert isinstance(ledger.events[0], FactRecorded)
    assert state.campaign is not None and state.campaign.complete
    if ending is not None and finale:
        apply_all(state, [FinaleChosen(option_id=ending)], log)
        assert campaign_complete(state)
    return start, state, log, final
