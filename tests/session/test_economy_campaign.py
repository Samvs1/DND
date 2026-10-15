"""Quests, milestones and rewards through the campaign (M5.6): events apply and replay exactly."""

from __future__ import annotations

from aidm.dm.tool_context import tool_registries
from aidm.models.campaign_events import RegionResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.dm_tiers import XpTier
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import AnyEvent, CreatureDied, GoldChanged, XpGained
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.models.world_events import LevelUpReady, QuestUpdated, RewardGranted
from aidm.rules.dm_tiers import xp_award
from aidm.rules.encounter import encounter_outcome, end_encounter
from aidm.rules.quest_rewards import (
    quest_transition_refusal,
    resolution_reward_events,
)
from aidm.session.reducer import replay
from tests.ai.tool_fixtures import run_tool
from tests.session.progression_fixtures import (
    answer,
    apply_all,
    campaign_state,
    move,
    plan,
    quest_moved,
)

REGS = tool_registries()
PCS = ("fighter", "rogue", "wizard", "cleric")


def _quest(state: GameState, quest_id: str, new: str, log: list[AnyEvent]) -> list[AnyEvent]:
    return apply_all(state, quest_moved(state, quest_id, QuestState(new)), log)


def _xp(state: GameState, pc_id: str) -> int:
    pc = state.creatures[pc_id].pc
    assert pc is not None
    return pc.xp


def _gold(state: GameState) -> int:
    return sum(c.pc.gold for c in state.creatures.values() if c.pc is not None)


def test_lifecycle_rules() -> None:
    assert quest_transition_refusal(None, QuestState.ACTIVE) is None
    assert quest_transition_refusal(QuestState.OFFERED, QuestState.ACTIVE) is None
    assert quest_transition_refusal(QuestState.ACTIVE, QuestState.COMPLETED) is None
    assert quest_transition_refusal(QuestState.ACTIVE, QuestState.FAILED) is None
    assert quest_transition_refusal(QuestState.OFFERED, QuestState.COMPLETED) is not None
    assert quest_transition_refusal(QuestState.ACTIVE, QuestState.OFFERED) is not None
    assert quest_transition_refusal(QuestState.COMPLETED, QuestState.ACTIVE) is not None


def test_offered_quest_cannot_be_completed_directly() -> None:
    _, state, _ = campaign_state()
    refused = run_tool(state, "update_quest", quest_id="missing-ledger")
    assert refused.error is not None and "not accepted" in refused.error and not refused.events


def test_completing_a_campaign_quest_pays_its_tier() -> None:
    start, state, log = campaign_state()
    _quest(state, "missing-ledger", "active", log)
    # M9.2: heroes start with their background purse (4 human acolytes: 15 gp each).
    before = _gold(state)
    assert before == 60
    events = _quest(state, "missing-ledger", "completed", log)
    paid = [e for e in events if isinstance(e, RewardGranted)]
    assert len(paid) == 1 and paid[0].kind == "quest" and paid[0].items == ("harbour-ledger",)
    # minor tier, level 1: 25 XP each (dm_tiers xp_by_level) and 25 gp each (quest_gold_gp, act 1).
    assert xp_award(REGS.tiers, XpTier.MINOR, 1) == 25
    assert [e.amount for e in events if isinstance(e, XpGained)] == [25] * 4
    assert sum(e.delta for e in events if isinstance(e, GoldChanged)) == 100
    assert _gold(state) == before + 100
    holders = [
        c.id
        for c in state.creatures.values()
        if c.pc is not None and any(r.item == "harbour-ledger" for r in c.pc.inventory)
    ]
    assert len(holders) == 1
    assert [_xp(state, p) for p in PCS] == [25] * 4
    again = run_tool(state, "update_quest", quest_id="missing-ledger")
    assert again.error is not None and "already completed" in again.error
    assert quest_moved(state, "missing-ledger", QuestState.COMPLETED)[1:] == []  # paid once
    assert replay(start, log) == state


def test_failing_a_quest_pays_nothing() -> None:
    _, state, log = campaign_state()
    _quest(state, "missing-ledger", "active", log)
    before = _gold(state)
    events = _quest(state, "missing-ledger", "failed", log)
    assert not any(isinstance(e, RewardGranted) for e in events) and _gold(state) == before


def test_an_invented_quest_pays_nothing() -> None:
    _, state, log = campaign_state()
    made = Quest(id="side-job", title="Side job", state=QuestState.ACTIVE)  # a pre-M23 save's
    apply_all(state, [QuestUpdated(quest=made)], log)
    events = _quest(state, "side-job", "completed", log)
    assert not any(isinstance(e, RewardGranted | XpGained | GoldChanged) for e in events)


def _win(state: GameState, log: list[AnyEvent]) -> None:
    enc = state.encounter
    assert enc is not None
    for cid, combatant in sorted(enc.combatants.items()):
        if combatant.side is Side.HOSTILE:
            apply_all(state, [CreatureDied(creature_id=cid)], log)
    assert encounter_outcome(state) is EncounterStatus.VICTORY
    apply_all(state, end_encounter(state, EncounterStatus.VICTORY), log)
    apply_all(state, resolution_reward_events(state, REGS.tiers, REGS.catalogue), log)


def test_region_resolution_pays_milestone_xp() -> None:
    start, state, log = campaign_state()
    region = plan().acts[0].region
    _tour_with_rewards(state, log, 0)
    mark = [e for e in log if isinstance(e, RewardGranted) and e.kind == "milestone"]
    assert len(mark) == 1 and mark[0].source == region.id
    # region tier 1 pays a moderate grant at level 1: 75 XP each (dm_tiers xp_by_level).
    assert mark[0].xp_each == 75
    assert replay(start, log) == state


def test_full_campaign_flags_level_ups_and_replays() -> None:
    start, state, log = campaign_state()
    for act in range(3):
        if act:
            move(state, plan().acts[act].region.arrival.id, log)
        _tour_with_rewards(state, log, act)
    finals = [e for e in log if isinstance(e, RegionResolved)]
    assert [e.final for e in finals] == [False, False, True]
    milestones = [e for e in log if isinstance(e, RewardGranted) and e.kind == "milestone"]
    assert [m.xp_each for m in milestones] == [75, 150, 300]  # moderate, major, major + final major
    assert any(isinstance(e, LevelUpReady) for e in log)
    assert replay(start, log) == state


def _tour_with_rewards(state: GameState, log: list[AnyEvent], act: int) -> None:
    region = plan().acts[act].region
    for spoke in region.spokes:
        if state.world.current_node != region.arrival.id:
            move(state, region.arrival.id, log)
        move(state, spoke.id, log)
        answer(state, OfferChoice.FIGHT, log)
        _win(state, log)
    move(state, region.gateway.id, log)
    answer(state, OfferChoice.FIGHT, log)
    _win(state, log)
