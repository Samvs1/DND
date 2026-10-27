"""M43.4 quest contract C1-C5 where a quest is registered (docs/next/M43_CONTRACT.md).

C1, C2, C4 cases are quests a round-8 table really registered (the saves are gitignored, so the
quest is written out here from the logged event); C3, C5 and the favour door use committed
fixtures."""

import pytest

from aidm.models.campaign import QuestPlan
from aidm.models.problem import Problem
from aidm.models.quests import QuestStep, StepKind
from aidm.rules.favours import FavourRefused, favour_events
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.plan_repair import repair_plan
from aidm.rules.quest_contract import fit_side_quest, fit_steps, target_refusal
from aidm.rules.quest_steps import step_met
from aidm.rules.quest_targets import party_friend
from tests.ai.chooser_fixtures import state_at
from tests.unit.contract.helpers import fixture

GERDA = "gerda-chainwright"


def _visit() -> QuestStep:
    return QuestStep(kind=StepKind.VISIT, text="Go to Gildspar Keep", nodes=("gildspar-keep",))


def _coiner() -> QuestPlan:
    """r8-quests (c-20261027-064955-0003) event 669: the quest asked by Gerda aims at Gerda and
    sends the party to Gildspar Keep twice."""
    find = QuestStep(
        kind=StepKind.OBTAIN,
        text="Find the False Gold Bar at Saltwell Sink",
        item="False Gold Bar",
        nodes=("saltwell-sink",),
        hidden=True,
    )
    meet = QuestStep(kind=StepKind.MEET, text="Meet Gerda Chainwright", npc=GERDA)
    return QuestPlan(
        id="the-coiner-s-false-gold",
        title="The Coiner's False Gold",
        giver_npc_id=GERDA,
        against_npc_id=GERDA,
        objective="Trace the false gold flooding the Barrens to its coiner.",
        reward_tier="minor",
        act=1,
        steps=(_visit(), _visit(), find, meet),
    )


def test_m43_c1_a_target_who_is_the_giver_is_cleared() -> None:
    """r8-quests 669: against_npc_id == giver_npc_id; the quest stays, without a target."""
    notes: list[Problem] = []
    fitted = fit_side_quest(_coiner(), notes)
    assert fitted is not None and fitted.against_npc_id is None
    assert any("giver was the target" in n.message for n in notes)


def test_m43_c1_a_defeat_step_aimed_at_the_giver_leaves_the_quest_out() -> None:
    notes: list[Problem] = []
    hit = QuestStep(kind=StepKind.DEFEAT, text="Defeat Gerda", npc=GERDA)
    quest = _coiner().model_copy(update={"steps": (hit,)})
    assert fit_side_quest(quest, notes) is None
    assert any("left out" in n.message for n in notes)


def test_m43_c1_the_target_rule_names_giver_and_friend() -> None:
    assert target_refusal("a", "a", False) is not None
    assert target_refusal("a", "b", True) is not None
    assert target_refusal("a", "b", False) is None
    assert target_refusal("a", None, True) is None


def test_m43_c2_a_repeated_step_is_dropped() -> None:
    """r8-quests 669: step 1 repeats step 0 (two "Go to Gildspar Keep")."""
    notes: list[Problem] = []
    steps = fit_steps("the-coiner-s-false-gold", _coiner().steps, notes)
    assert [s.kind for s in steps] == [StepKind.VISIT, StepKind.OBTAIN, StepKind.MEET]
    assert len(notes) == 1


def test_m43_c2_a_free_step_is_dropped_while_a_checked_step_remains() -> None:
    """m29-r2-p8 774, A Name for the Road: a step the engine cannot check."""
    free = QuestStep(kind=StepKind.FREE, text="Think of a name")
    steps = fit_steps("q", (free, _visit()), [])
    assert [s.kind for s in steps] == [StepKind.VISIT]
    assert fit_steps("q", (free,), []) == (free,)


def test_m43_c4_find_three_hand_over_one_use_one_count() -> None:
    """r8-full (c-20261027-064955-0001) 127, The Painted Eggs: find 3, hand over 1."""
    find = QuestStep(
        kind=StepKind.OBTAIN,
        text="Find 3 x Painted clutch eggs at Bog Hollow",
        item="Painted clutch eggs",
        nodes=("bog-hollow",),
        count=3,
        hidden=True,
    )
    give = QuestStep(
        kind=StepKind.DELIVER, text="Give the eggs", item="Painted clutch eggs", npc="mara-ost"
    )
    out = fit_steps("the-painted-eggs", (find, give), [])
    assert [s.count for s in out] == [1, 1]


def test_m43_c4_the_reward_is_never_the_item_asked() -> None:
    """m29-r2-p5 install, The Millstone's Secret: the reward 'Grey Flour Charm' was asked for."""
    installed = next(
        e.event for e in fixture("m29-r2-p5").events if e.event.type == "campaign_installed"
    )
    plan = repair_plan(installed.plan, [])
    quest = next(q for q in plan.quests if q.id == "the-millstone-s-secret")
    assert quest.reward_item != "Grey Flour Charm" and "Flour" not in (quest.reward_item or "")


def test_m43_c3_a_step_met_only_from_what_happened_after_acceptance() -> None:
    """m39-r7-full 444: the fight at the Grey Bog counted the moment Straighten the River was
    accepted. The engine's own check, which decides every quest_step_done, says not yet."""
    state = state_at("m39-r7-full", 444)
    quest = state.world.quests["straighten-the-river"]
    assert quest.steps[0].kind is StepKind.CLEAR
    assert not step_met(state, quest.steps[0], quest.id)


def test_m43_c5_a_route_ending_at_the_master_ends_with_a_hand_over_or_a_meet() -> None:
    """m29-p2 plan: every route whose last step names the master hands over or meets (the engine
    finishes both while the master's offer waits, `quest_progress._peace_deeds`, M29.7c R14)."""
    installed = next(
        e.event for e in fixture("m29-p2").events if e.event.type == "campaign_installed"
    )
    last = [
        r.steps[-1]
        for a in installed.plan.acts
        for r in (a.main.routes if a.main else ())
        if r.steps[-1].npc == boss_npc_id(a.region)
    ]
    assert last and all(s.kind in (StepKind.DELIVER, StepKind.MEET) for s in last)


def test_m43_favour_against_a_friend_is_refused() -> None:
    """m39-r7-full 436: Bram asks the party to defeat Isca Murkline, who is a friend."""
    state = state_at("m39-r7-full", 436)
    assert party_friend(state, "isca-murkline")
    step = QuestStep(kind=StepKind.DEFEAT, text="Defeat Isca", npc="isca-murkline")
    with pytest.raises(FavourRefused, match="friend"):
        favour_events(state, "bram-coldbrook", "Settle the bog", step)
