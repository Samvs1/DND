"""Loot after a victory (aidm.rules.loot) and the shared payout path (aidm.rules.rewards)."""

from __future__ import annotations

import random

from aidm.data.combat_data import combat_registries
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import (
    CampSuppliesChanged,
    CreatureDied,
    EncounterEnded,
    GoldChanged,
    InventoryChanged,
    XpGained,
)
from aidm.models.state import GameState
from aidm.models.world_events import LevelUpReady, RewardGranted
from aidm.rules.encounter import start_encounter
from aidm.rules.loot import (
    end_encounter_with_loot,
    loot_kind,
    loot_payout,
    loot_rng,
    victory_loot_events,
)
from aidm.rules.rewards import Payout, gold_shares, payout_events
from tests.sim.sim_setup import setup_fight
from tests.unit.rules.economy_fixtures import CAT, LOOT, apply_events, gold_of

REGS = combat_registries()


def fight(seed: int = 3, kill: bool = True) -> GameState:
    state, setup, rng, _, _ = setup_fight(seed)
    apply_events(state, start_encounter(rng, state, setup, REGS.monsters))
    enc = state.encounter
    assert enc is not None
    if kill:
        for cid, combatant in sorted(enc.combatants.items()):
            if combatant.side is Side.HOSTILE:
                apply_events(state, [CreatureDied(creature_id=cid)])
    return state


def test_gold_shares_sum_to_the_total() -> None:
    assert gold_shares(10, 4) == [3, 3, 2, 2]
    assert sum(gold_shares(7, 3)) == 7
    assert gold_shares(5, 0) == []


def test_loot_is_deterministic_for_a_seed() -> None:
    state = fight()
    first = loot_payout(state, LOOT, loot_rng(state))
    again = loot_payout(state, LOOT, loot_rng(state))
    assert first == again
    assert first.gold_total > 0 or first.items or first.supplies


def test_loot_uses_the_table_numbers() -> None:
    state = fight()
    enc = state.encounter
    assert enc is not None
    foes = [c for c in enc.combatants.values() if c.side is Side.HOSTILE]
    tier_tables = LOOT.tiers[str(state.world.region_tier)]
    most_gold = 0
    for combatant in foes:
        kind = loot_kind(state, state.creatures[combatant.creature_id])
        table = tier_tables.get(kind, tier_tables["default"])
        top = {"1d6": 6, "2d6": 12, "0": 0, "1d8": 8}.get(table.gold, 999)
        most_gold += top
    payout = loot_payout(state, LOOT, loot_rng(state))
    assert 0 <= payout.gold_total <= most_gold
    assert all(item in CAT for item in payout.items)


def test_victory_loot_events_are_applied_to_the_party() -> None:
    state = fight(seed=5)
    rng = random.Random(1)
    events = end_encounter_with_loot(state, EncounterStatus.VICTORY, LOOT, CAT, rng)
    assert any(isinstance(e, EncounterEnded) for e in events)
    rewards = [e for e in events if isinstance(e, RewardGranted)]
    if rewards:
        assert rewards[0].kind == "loot"
    before = sum(gold_of(state, p) for p in ("fighter", "rogue", "wizard", "cleric"))
    apply_events(state, events)
    after = sum(gold_of(state, p) for p in ("fighter", "rogue", "wizard", "cleric"))
    paid = sum(e.delta for e in events if isinstance(e, GoldChanged))
    assert after - before == paid


def test_no_loot_without_a_victory() -> None:
    state = fight()
    events = end_encounter_with_loot(state, EncounterStatus.FLED, LOOT, CAT, random.Random(1))
    assert not any(isinstance(e, RewardGranted) for e in events)


def test_victory_loot_events_alone() -> None:
    state = fight(seed=4)
    events = victory_loot_events(state, LOOT, CAT, loot_rng(state))
    assert all(
        isinstance(e, RewardGranted | GoldChanged | InventoryChanged | CampSuppliesChanged)
        for e in events
    )


def test_payout_shares_xp_gold_items_and_supplies() -> None:
    state = fight(seed=5, kill=False)  # seed 5: a level-1 party, so 350 XP is level 2
    payout = Payout(
        xp_each=350, gold_total=10, items=("iron-key", "camp-ration", "iron-key"), supplies=2
    )
    events = payout_events(state, payout, "test", "quest", CAT)
    assert isinstance(events[0], RewardGranted) and events[0].gold_each == 2
    assert sum(e.amount for e in events if isinstance(e, XpGained)) == 350 * 4
    assert sum(e.delta for e in events if isinstance(e, GoldChanged)) == 10
    ups = [e for e in events if isinstance(e, LevelUpReady)]
    assert len(ups) == 4 and all(e.level == 2 for e in ups)
    supply = [e for e in events if isinstance(e, CampSuppliesChanged)]
    assert len(supply) == 1 and supply[0].delta == 3
    keys = [e for e in events if isinstance(e, InventoryChanged) and e.item == "iron-key"]
    assert sum(e.delta for e in keys) == 2


def test_empty_payout_makes_no_events() -> None:
    state = fight(kill=False)
    assert payout_events(state, Payout(), "x", "loot", CAT) == []
