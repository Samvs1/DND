"""Spoke milestones and campaign pacing (M9.2, RULES_DECISIONS M9.2).

A spoke pays `spoke_visit_xp_tier` (minor) on its first visit and `spoke_clear_xp_tier`
(moderate) when a fight there is won or a parley succeeds, each once (`CampaignState.milestones`).
Pacing: act 1's spokes alone take a level-1 party to level 2; the full sample campaign ends
with the party at level 4-5 before the final boss.
"""

from aidm.models.campaign_state import OfferChoice
from aidm.models.dm_tiers import XpTier
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import AnyEvent, CampSuppliesChanged, CreatureDied, XpGained
from aidm.models.state import GameState
from aidm.models.world_events import LevelUpReady, RewardGranted
from aidm.rules.campaign_install import boss_npc_id
from aidm.rules.dm_tiers import xp_award
from aidm.rules.encounter import end_encounter
from aidm.rules.leveling import can_level_up
from aidm.rules.milestones import clear_key, milestone_events, visit_key
from aidm.rules.quest_rewards import resolution_reward_events
from aidm.rules.rests import STARTING_CAMP_SUPPLIES
from aidm.session.reducer import replay
from tests.session.progression_fixtures import (
    REGS,
    Rigged,
    answer,
    apply_all,
    campaign_state,
    move,
    pending,
    plan,
)
from tests.sim.sim_setup import REGS as COMBAT_REGS
from tests.unit.rules.leveling_fixtures import level_to

R1 = plan().acts[0].region


def _go(state: GameState, node: str, log: list[AnyEvent]) -> list[AnyEvent]:
    """Travel (with the arrival offer), then the milestones the move earned."""
    moved = list(log)
    move(state, node, log)
    batch = log[len(moved) :]
    return apply_all(state, milestone_events(state, batch, REGS.tiers, REGS.catalogue), log)


def _won(state: GameState, log: list[AnyEvent]) -> list[AnyEvent]:
    """Fight the pending offer and win it; then region rewards and milestones, as a session."""
    mark = len(log)
    answer(state, OfferChoice.FIGHT, log)
    enc = state.encounter
    assert enc is not None
    for cid, combatant in sorted(enc.combatants.items()):
        if combatant.side is Side.HOSTILE:
            apply_all(state, [CreatureDied(creature_id=cid)], log)
    apply_all(state, end_encounter(state, EncounterStatus.VICTORY), log)
    apply_all(state, resolution_reward_events(state, REGS.tiers, REGS.catalogue), log)
    batch = log[mark:]
    return apply_all(state, milestone_events(state, batch, REGS.tiers, REGS.catalogue), log)


def _xp(state: GameState) -> list[int]:
    return sorted(c.pc.xp for c in state.creatures.values() if c.pc is not None)


def test_install_gives_the_starting_camp_supplies() -> None:
    _, state, log = campaign_state()
    # One BG3 long rest for a party of four: 4 x 10 supplies (RULES_DECISIONS M1.6 / M9.2).
    assert STARTING_CAMP_SUPPLIES == 40
    assert state.camp_supplies == 40
    assert [e.delta for e in log if isinstance(e, CampSuppliesChanged)] == [40]


def test_spoke_visit_and_clear_pay_once() -> None:
    start, state, log = campaign_state()
    spoke = R1.spokes[0].id
    visit = _go(state, spoke, log)
    # minor tier at level 1: 25 XP each (dm_tiers xp_by_level).
    assert xp_award(REGS.tiers, XpTier.MINOR, 1) == 25
    paid = [e for e in visit if isinstance(e, RewardGranted)]
    assert [(e.source, e.kind, e.xp_each) for e in paid] == [(visit_key(spoke), "milestone", 25)]
    before = _xp(state)
    cleared = _won(state, log)
    paid = [e for e in cleared if isinstance(e, RewardGranted)]
    # moderate tier at level 1: 75 XP each.
    assert [(e.source, e.xp_each) for e in paid] == [(clear_key(spoke), 75)]
    assert all(after >= b + 75 for after, b in zip(_xp(state), before, strict=True))
    assert state.campaign is not None
    assert state.campaign.milestones == [visit_key(spoke), clear_key(spoke)]
    _go(state, R1.arrival.id, log)
    again = _go(state, spoke, log)
    assert not any(isinstance(e, RewardGranted) for e in again)
    assert replay(start, log) == state


def test_arrival_and_gateway_pay_no_spoke_milestone() -> None:
    _, state, log = campaign_state()
    for spoke in R1.spokes:
        if state.world.current_node != R1.arrival.id:
            _go(state, R1.arrival.id, log)
        _go(state, spoke.id, log)
        _won(state, log)
    earned = _go(state, R1.gateway.id, log)
    assert not any(isinstance(e, RewardGranted) for e in earned)
    assert pending(state).boss_npc_id == boss_npc_id(R1)


def test_successful_parley_clears_the_spoke() -> None:
    _, state, log = campaign_state()
    spoke = R1.spokes[1].id
    _go(state, spoke, log)
    mark = len(log)
    answer(state, OfferChoice.PARLEY, log, rng=Rigged(high=True))
    earned = apply_all(state, milestone_events(state, log[mark:], REGS.tiers, REGS.catalogue), log)
    assert [e.source for e in earned if isinstance(e, RewardGranted)] == [clear_key(spoke)]


def test_act_one_spokes_reach_level_two_naturally() -> None:
    _, state, log = campaign_state()
    for spoke in R1.spokes:
        if state.world.current_node != R1.arrival.id:
            _go(state, R1.arrival.id, log)
        _go(state, spoke.id, log)
        _won(state, log)
    # 3 spokes x (25 + 75) milestone XP + kill XP >= 300 (SRD level 2).
    assert min(_xp(state)) >= 300
    ready = {e.creature_id for e in log if isinstance(e, LevelUpReady) and e.level == 2}
    assert len(ready) == 4


def _level_ups(state: GameState, log: list[AnyEvent]) -> None:
    for cid, creature in sorted(state.creatures.items()):
        if creature.pc is not None and can_level_up(creature):
            level_to(state, cid, creature.pc.level + 1, COMBAT_REGS.chars, log)


def _tour(state: GameState, log: list[AnyEvent], act: int) -> int:
    """Clear every spoke of `act` (levelling up as soon as possible); return the level at the
    boss, then win the boss fight."""
    region = plan().acts[act].region
    if act:
        _go(state, region.arrival.id, log)
    for spoke in region.spokes:
        if state.world.current_node != region.arrival.id:
            _go(state, region.arrival.id, log)
        _go(state, spoke.id, log)
        _won(state, log)
        _level_ups(state, log)
    _go(state, region.gateway.id, log)
    level = min(c.pc.level for c in state.creatures.values() if c.pc is not None)
    if act == 0:
        # The boss and its company are rated hard for the actual party (four level-2 heroes).
        assert pending(state).difficulty == "hard"
    _won(state, log)
    _level_ups(state, log)
    return level


def test_campaign_pacing_reaches_level_four_or_five_by_the_final_boss() -> None:
    start, state, log = campaign_state()
    levels = [_tour(state, log, act) for act in range(3)]
    # Act 1's boss at level 2, act 2's at 3-4, the final boss at 4-5 (BG3-like curve).
    assert levels[0] == 2
    assert 3 <= levels[1] <= 4
    assert 4 <= levels[2] <= 5
    assert sum(isinstance(e, XpGained) for e in log) > 0
    assert replay(start, log) == state
