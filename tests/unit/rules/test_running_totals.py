"""M35.1 (round-6 Y1): `chain_totals` makes payouts read from one state build on each other."""

from __future__ import annotations

from aidm.models.events import (
    AnyEvent,
    CampSuppliesChanged,
    GoldChanged,
    InventoryChanged,
    LongRestTaken,
    XpGained,
)
from aidm.models.world_events import LevelUpReady
from aidm.rules.rewards import Payout, payout_events
from aidm.rules.running_totals import chain_totals
from scripts.sim.ledger import ledger_problems
from tests.unit.rules.economy_fixtures import CAT, PARTY_IDS, apply_events, carried, gold_of
from tests.unit.rules.economy_fixtures import shop_state as party_with_gold


def _two_payouts() -> tuple[list[AnyEvent], list[AnyEvent]]:
    state = party_with_gold(gold=10)
    first = payout_events(
        state, Payout(xp_each=150, gold_total=40, items=("iron-key",)), "a", "quest", CAT
    )
    second = payout_events(
        state, Payout(xp_each=200, gold_total=80, items=("iron-key",)), "b", "quest", CAT
    )
    return first, second


def test_unchained_payouts_from_one_state_lose_the_first() -> None:
    """The Y1 shape: both payouts write their totals from the same snapshot."""
    state = party_with_gold(gold=10)
    first, second = _two_payouts()
    apply_events(state, [*first, *second])
    assert gold_of(state) == 10 + 20  # the first payout's 10 gp each are gone
    assert ledger_problems(party_with_gold(gold=10), [*first, *second]) != []


def test_golden_chained_payouts_both_land() -> None:
    start = party_with_gold(gold=10)
    first, second = _two_payouts()
    chained = chain_totals(start, [*first, *second])
    state = apply_events(start.model_copy(deep=True), chained)
    for pc_id in PARTY_IDS:
        assert gold_of(state, pc_id) == 10 + 10 + 20  # 40 gp and 80 gp shared by four
        pc = state.creatures[pc_id].pc
        assert pc is not None and pc.xp == 350
    keys = sum(carried(state, "iron-key", pc_id) for pc_id in PARTY_IDS)
    assert keys == 2
    assert ledger_problems(start, chained) == []
    # the deltas are untouched: only the new values move
    assert [e.amount for e in chained if isinstance(e, XpGained)] == [150] * 4 + [200] * 4


def test_level_up_flag_follows_the_running_xp() -> None:
    """150 + 200 crosses 300 XP (SRD level 2) only on the second payout: one flag each, there."""
    start = party_with_gold(gold=10)
    first, second = _two_payouts()
    assert not any(isinstance(e, LevelUpReady) for e in [*first, *second])  # each alone: no
    chained = chain_totals(start, [*first, *second])
    flags = [i for i, e in enumerate(chained) if isinstance(e, LevelUpReady)]
    assert len(flags) == len(PARTY_IDS)
    gains = [chained[i - 1] for i in flags]
    assert [e.amount for e in gains if isinstance(e, XpGained)] == [200] * len(PARTY_IDS)


def test_a_doubled_flag_is_dropped() -> None:
    start = party_with_gold(gold=0)
    big = payout_events(start, Payout(xp_each=320), "a", "milestone", CAT)
    chained = chain_totals(start, [*big, *big])
    assert len([e for e in chained if isinstance(e, LevelUpReady)]) == len(PARTY_IDS)


def test_supplies_chain_and_a_rest_resets_the_pool() -> None:
    start = party_with_gold(gold=0)
    pool = start.camp_supplies
    events: list[AnyEvent] = [
        CampSuppliesChanged(delta=3, camp_supplies=pool + 3),
        CampSuppliesChanged(delta=2, camp_supplies=pool + 2),
        LongRestTaken(supplies_spent=pool + 5, camp_supplies=0),
        CampSuppliesChanged(delta=1, camp_supplies=pool + 1),
    ]
    chained = chain_totals(start, events)
    pools = [e.camp_supplies for e in chained if isinstance(e, CampSuppliesChanged)]
    assert pools == [pool + 3, pool + 5, 1]


def test_non_pc_and_other_events_pass_through() -> None:
    start = party_with_gold(gold=0)
    odd: list[AnyEvent] = [
        GoldChanged(creature_id="nobody", delta=5, gold=7),
        InventoryChanged(creature_id="nobody", item="rope", delta=1, qty=9),
    ]
    assert chain_totals(start, odd) == odd
