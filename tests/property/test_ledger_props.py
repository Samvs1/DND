"""Property (M35.1, round-6 Y1): generated play keeps every absolute equal to its running value.

Batches of payouts built from ONE state (as the quest pass, milestones and fight ends build them)
are chained and applied; every gold, XP, item and supply total in the log must equal the value
before it plus its change (`scripts.sim.ledger`), and every hero ends with the sum of its shares.
A second property finishes any subset of the act-1 side quests on the same step through the
session's settle loop and checks the same ledger.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.models.events import AnyEvent
from aidm.models.world import QuestState
from aidm.models.world_events import QuestUpdated, RewardGranted
from aidm.rules.rewards import Payout, payout_events
from aidm.rules.running_totals import chain_totals
from aidm.session.quest_flow import settle_after
from scripts.sim.ledger import ledger_problems
from tests.session.progression_fixtures import REGS, apply_all, campaign_state
from tests.unit.rules.economy_fixtures import CAT, PARTY_IDS, apply_events, gold_of
from tests.unit.rules.economy_fixtures import shop_state as party_with_gold

ITEMS = ("iron-key", "camp-ration", "rope-hempen-50-feet", "torch")
PAYOUTS = st.builds(
    Payout,
    xp_each=st.integers(0, 400),
    gold_total=st.integers(0, 200),
    items=st.lists(st.sampled_from(ITEMS), max_size=4).map(tuple),
    supplies=st.integers(0, 3),
)


@settings(max_examples=40, deadline=None)
@given(batches=st.lists(st.lists(PAYOUTS, min_size=1, max_size=4), min_size=1, max_size=4))
def test_chained_payout_batches_keep_the_ledger(batches: list[list[Payout]]) -> None:
    start = party_with_gold(gold=5)
    state = start.model_copy(deep=True)
    log: list[AnyEvent] = []
    for batch in batches:
        built = [
            e
            for i, p in enumerate(batch)
            for e in payout_events(state, p, f"p{len(log)}-{i}", "quest", CAT)
        ]
        chained = chain_totals(state, built)
        apply_events(state, chained)
        log += chained
    assert ledger_problems(start, log) == []
    shares = [e.gold_each for e in log if isinstance(e, RewardGranted)]
    assert gold_of(state, max(PARTY_IDS)) == 5 + sum(shares)  # the last id gets no remainder


@settings(max_examples=8, deadline=None)
@given(data=st.data())
def test_quests_finishing_together_keep_the_ledger(data: st.DataObject) -> None:
    start, state, log = campaign_state()
    side = sorted(q.id for q in state.world.quests.values() if q.state is QuestState.OFFERED)
    chosen = data.draw(st.lists(st.sampled_from(side), unique=True, min_size=1))
    updates: list[AnyEvent] = []
    for qid in chosen:
        quest = state.world.quests[qid]
        done = {"state": QuestState.ACTIVE, "steps_done": len(quest.steps)}
        updates.append(QuestUpdated(quest=quest.model_copy(update=done)))
    apply_all(state, updates, log)
    settle_after(state, REGS, [], lambda events: apply_all(state, events, log))
    assert all(state.world.quests[q].state is QuestState.COMPLETED for q in chosen)
    assert ledger_problems(start, log) == []
