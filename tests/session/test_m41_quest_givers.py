"""M41.4 round 7 Z14 Z15 (docs/playtests/M39_round7.md): a task is handed in where it was given,
never targets the party's friend, and counts only a fight won after it was accepted.

- Z14, r7b-quests 680-684: The Brief Life of War (giver Duscia Vane at Rookery Hill) closed on
  its second visit step at Briarfall Keep and paid at once. Now its report to Duscia joins it as
  the last step and it pays only at Rookery Hill.
- Z15, r7b-full 436-444: Bram's "Straighten the River" was asked against Isca Murkline, whom the
  party had just fought for, and "Win the fight at The Grey Bog" closed at once from that earlier
  fight (the Y7 sub-case). Now Isca is no target and meeting her replaces defeating her; the bog
  already won is a visit; and the old clear is never credited after the acceptance.
"""

from aidm.models.events import AnyEvent
from aidm.models.quest_events import QuestStepAdded, QuestStepDone
from aidm.models.quests import MAX_STEPS, StepKind
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.models.world_events import PartyMoved, QuestUpdated, RewardGranted
from aidm.rules.plan_repair import repair_plan
from aidm.rules.plan_tasks import ends_at
from aidm.rules.quest_offers import ask_events
from aidm.rules.quest_steps import place_won
from aidm.rules.quest_targets import party_friend
from aidm.session.quest_flow import settle_after
from scripts.sim.ledger import ledger_problems
from tests.session.playtest_saves import FIXTURES, events_of, logged, replay_until
from tests.session.progression_fixtures import REGS, apply_all

QUESTS, FULL = "m39-r7-quests", "m39-r7-full"
BRIEF, RIVER = "the-brief-life-of-war", "straighten-the-river"
Y1_LOG = "m35-r6-typed"
Y1_WRITES = tuple(f"event {i} " for i in range(678, 686))


def _settle(state: GameState, batch: list[AnyEvent], log: list[AnyEvent]) -> list[AnyEvent]:
    return settle_after(state, REGS, batch, lambda events: apply_all(state, events, log))


def _paid(events: list[AnyEvent], source: str) -> bool:
    return any(isinstance(e, RewardGranted) and e.source == source for e in events)


def test_v1_z14_brief_life_waits_for_its_giver() -> None:
    state = replay_until(QUESTS, 680)
    log: list[AnyEvent] = [e.event for e in events_of(QUESTS) if e.seq < 680]
    out = _settle(state, [], log)
    quest = state.world.quests[BRIEF]
    assert quest.state is QuestState.ACTIVE and not _paid(out, BRIEF)
    assert [(s.kind, s.npc) for s in quest.steps][-1] == (StepKind.MEET, "duscia-vane")
    assert quest.steps[-1].text == "Meet Duscia Vane"
    assert quest.steps_done == len(quest.steps) - 1
    assert any(isinstance(e, QuestStepAdded) and e.quest_id == BRIEF for e in out)


def test_v1_z14_brief_life_pays_at_rookery_hill() -> None:
    state = replay_until(QUESTS, 680)
    log: list[AnyEvent] = [e.event for e in events_of(QUESTS) if e.seq < 680]
    _settle(state, [], log)
    here = state.world.current_node
    moved = PartyMoved(
        from_node=here, to_node="rookery-hill", scene_index=state.world.scene_index + 1
    )
    out = _settle(state, apply_all(state, [moved], log), log)
    assert state.world.quests[BRIEF].state is QuestState.COMPLETED
    assert _paid(out, BRIEF)
    assert ledger_problems(replay_until(QUESTS, 0), log) == []


def test_r7_plans_hand_every_side_quest_in_at_its_giver() -> None:
    for run, seq in ((QUESTS, 680), (FULL, 436)):
        campaign = replay_until(run, seq).campaign
        assert campaign is not None
        for quest in repair_plan(campaign.plan, []).quests:
            assert ends_at(quest.steps, quest.giver_npc_id) or len(quest.steps) == MAX_STEPS


def test_v1_z15_river_is_asked_without_its_friend_as_target() -> None:
    state = replay_until(FULL, 436)
    assert party_friend(state, "isca-murkline")  # the party fought for her (deeds 10)
    asked = ask_events(state, [logged(FULL, 435).event])
    quest = next(e.quest for e in asked if isinstance(e, QuestUpdated) and e.quest.id == RIVER)
    assert quest.against_npc_id is None
    assert [(s.kind, s.text) for s in quest.steps] == [
        (StepKind.VISIT, "Go to The Grey Bog"),
        (StepKind.MEET, "Meet Isca Murkline"),
    ]


def test_v1_z15_an_old_fight_never_closes_a_new_step() -> None:
    state = replay_until(FULL, 444)
    accepted = state.world.quests[RIVER].active_since
    assert accepted is not None and accepted > 391  # the bog was won at 391, before the quest
    assert not place_won(state, "the-grey-bog", accepted)
    assert place_won(state, "the-grey-bog")
    log: list[AnyEvent] = [e.event for e in events_of(FULL) if e.seq < 444]
    out = _settle(state, [], log)
    assert not any(isinstance(e, QuestStepDone) and e.quest_id == RIVER for e in out)
    assert state.world.quests[RIVER].steps_done == 0
    assert ledger_problems(replay_until(FULL, 0), log) == []


def test_ledger_has_no_problems_on_any_playtest_fixture() -> None:
    """Every playtest log's totals are its running values. m35-r6-typed is the log of the Y1 bug
    itself (678: the second quest payout overwrote the first, fixed by M35.1, old logs keep their
    values): exactly those writes, nothing else."""
    runs = sorted(p.name for p in FIXTURES.iterdir() if (p / "initial.json").is_file())
    assert QUESTS in runs and FULL in runs
    for run in runs:
        name = run if run.startswith(("m3", "m4")) else run.removeprefix("m29-")
        events = [e.event for e in events_of(name)]
        problems = ledger_problems(replay_until(name, 0), events, limit=100)
        if run == Y1_LOG:
            assert problems and all(p.startswith(Y1_WRITES) for p in problems), problems
        else:
            assert problems == [], run
