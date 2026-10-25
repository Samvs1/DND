"""Property (M23.2): after any walk through sample act 1 with quests accepted, settling is a fixed
point (a second settle moves nothing), no quest pays twice and the log replays to the state."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.models.events import AnyEvent, event_adapter
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.models.world_events import QuestUpdated, RewardGranted
from aidm.session.quest_flow import settle_after
from aidm.session.reducer import replay
from scripts.sim.ledger import ledger_problems
from tests.session.progression_fixtures import REGS, apply_all, campaign_state, move


def _settle(state: GameState, batch: list[AnyEvent], log: list[AnyEvent]) -> list[AnyEvent]:
    return settle_after(state, REGS, batch, lambda events: apply_all(state, events, log))


@settings(max_examples=12, deadline=None)
@given(data=st.data())
def test_settling_is_idempotent_and_replays(data: st.DataObject) -> None:
    start, state, log = campaign_state()
    _settle(state, list(log), log)
    for quest in sorted(state.world.quests.values(), key=lambda q: q.id):
        if quest.state is QuestState.OFFERED and data.draw(st.booleans()):
            active = quest.model_copy(update={"state": QuestState.ACTIVE})
            apply_all(state, [QuestUpdated(quest=active)], log)
    for _ in range(data.draw(st.integers(min_value=1, max_value=6))):
        exits = sorted(state.world.neighbours.get(state.world.current_node or "", []))
        exits = [n for n in exits if n not in state.world.locked_nodes]
        if not exits or (state.campaign is not None and state.campaign.offer is not None):
            break
        mark = len(log)
        move(state, data.draw(st.sampled_from(exits)), log)
        _settle(state, log[mark:], log)
    assert _settle(state, [], log) == []
    sources = [e.source for e in log if isinstance(e, RewardGranted)]
    assert len(sources) == len(set(sources))
    decoded = [event_adapter.validate_json(e.model_dump_json()) for e in log]
    assert replay(start, decoded).model_dump() == state.model_dump()
    assert ledger_problems(start, log) == []  # M35.1 Y1: every total is the running one
