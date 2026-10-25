"""M35.1 round-6 Y1: quests finishing in the same pass all pay out in full (they were read from
one state, so the second payout's gold and XP overwrote the first's)."""

from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.models.world_events import AttitudeChanged, LevelUpReady, QuestUpdated, RewardGranted
from aidm.rules.dm_tiers import deed_points
from aidm.rules.quest_progress import quest_progress_events
from aidm.rules.social_deeds import QUEST_DEED_TIER
from aidm.session.quest_flow import settle_after
from scripts.sim.ledger import ledger_problems
from tests.session.progression_fixtures import REGS, apply_all, campaign_state

LEDGER, CHOIR = "missing-ledger", "douse-the-choir"


def _all_steps_done(state: GameState, quest_ids: tuple[str, ...], giver: str | None = None) -> None:
    """Accept the quests with every step already recorded (what one action finishing both does)."""
    events: list[AnyEvent] = []
    for qid in quest_ids:
        quest = state.world.quests[qid]
        update: dict[str, object] = {"state": QuestState.ACTIVE, "steps_done": len(quest.steps)}
        if giver is not None:
            update["giver_npc_id"] = giver
        events.append(QuestUpdated(quest=quest.model_copy(update=update)))
    apply_all(state, list(events))


def _purse(state: GameState) -> dict[str, tuple[int, int]]:
    return {
        cid: (c.pc.gold, c.pc.xp) for cid, c in sorted(state.creatures.items()) if c.pc is not None
    }


def test_golden_two_quest_payouts_one_step() -> None:
    start, state, log = campaign_state()
    _all_steps_done(state, (LEDGER, CHOIR))
    before = _purse(state)
    one_pass = quest_progress_events(state, REGS.tiers, REGS.catalogue)
    paid = [e.source for e in one_pass if isinstance(e, RewardGranted)]
    assert paid == [CHOIR, LEDGER]  # both finish in the SAME pass
    apply_all(state, one_pass, log)
    for cid, (gold, xp) in _purse(state).items():
        # data/bg3/dm_tiers.json act 1 quest gold per hero: minor 25 + moderate 60 = 85 gp;
        # xp_by_level at level 1: minor 25 + moderate 75 = 100 XP (both quests in full).
        assert gold == before[cid][0] + 85, cid
        assert xp == before[cid][1] + 100, cid
    assert ledger_problems(start, log) == []


def test_v1_y1_two_quests_settle_pays_both() -> None:
    """Through the session's settle loop: both quests complete and every hero gets both shares."""
    start, state, log = campaign_state()
    _all_steps_done(state, (LEDGER, CHOIR))
    before = _purse(state)
    settle_after(state, REGS, [], lambda events: apply_all(state, events, log))
    assert {q: state.world.quests[q].state for q in (LEDGER, CHOIR)} == {
        LEDGER: QuestState.COMPLETED,
        CHOIR: QuestState.COMPLETED,
    }
    gained = {cid: gold - before[cid][0] for cid, (gold, _) in _purse(state).items()}
    assert set(gained.values()) == {85}
    assert ledger_problems(start, log) == []


def test_two_quests_same_giver_both_deeds_land() -> None:
    """Deeds carry absolute values: the second quest of the same giver waits one pass."""
    start, state, log = campaign_state()
    giver = state.world.quests[LEDGER].giver_npc_id
    assert giver is not None
    _all_steps_done(state, (LEDGER, CHOIR), giver=giver)
    deeds = state.world.npcs[giver].deeds
    first = quest_progress_events(state, REGS.tiers, REGS.catalogue)
    assert len([e for e in first if isinstance(e, AttitudeChanged) and e.npc_id == giver]) == 1
    apply_all(state, first, log)
    settle_after(state, REGS, [], lambda events: apply_all(state, events, log))
    assert state.world.quests[CHOIR].state is QuestState.COMPLETED
    assert state.world.npcs[giver].deeds == deeds + 2 * deed_points(REGS.tiers, QUEST_DEED_TIER)
    assert ledger_problems(start, log) == []


def test_level_up_flag_once_across_two_payouts() -> None:
    """Two payouts that together cross a level threshold flag it once, at the crossing."""
    _, state, _ = campaign_state()
    _all_steps_done(state, (LEDGER, CHOIR))
    for creature in state.creatures.values():
        if creature.pc is not None:
            creature.pc.xp = 210  # 210 + 75 < 300 <= 210 + 75 + 25 (SRD level 2 at 300 XP)
    events = quest_progress_events(state, REGS.tiers, REGS.catalogue)
    flags = [e.creature_id for e in events if isinstance(e, LevelUpReady)]
    heroes = sorted(c.id for c in state.creatures.values() if c.pc is not None)
    assert sorted(flags) == heroes
