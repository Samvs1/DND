"""M23.4 quests come from people: no bulk offering, leads, the giver's ask, Accept / Not now,
leaving a region (the crossing question, left behind) and old saves. Rules + the settle helper.
"""

import random
from pathlib import Path

import pytest

from aidm.dm.event_text import event_line
from aidm.dm.narration_templates import template_line
from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.models.events import AnyEvent, event_adapter
from aidm.models.quest_events import (
    QuestAskDeclined,
    QuestAsked,
    QuestLeadAdded,
    QuestLeadRemoved,
)
from aidm.models.quests import StepKind
from aidm.models.state import GameState
from aidm.models.world import ClosedReason, Quest, QuestAsk, QuestState
from aidm.models.world_events import PartyMoved, QuestUpdated
from aidm.rules.quest_leaving import crossing, crossing_prompt, left_behind_events
from aidm.rules.quest_offers import QuestOfferRefused, answer_events, ask_events, lead_events
from aidm.session.reducer import apply, replay
from aidm.session.reducer_errors import ReducerError
from tests.ai.tool_fixtures import tool_call
from tests.session.progression_fixtures import REGS, apply_all, campaign_state, move, plan
from tests.session.quest_offer_fixtures import (
    R1,
    R2,
    accept,
    fight_won,
    fresh,
    go,
    resolve_region_one,
    settle,
    slendee_in_act_two,
)

LEDGER = "missing-ledger"
CHOIR = "douse-the-choir"
SIGNET = "wardens-signet"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "plan_weight_of_echoes.json"


def _replays(start: GameState, state: GameState, log: list[AnyEvent]) -> None:
    decoded = [event_adapter.validate_json(e.model_dump_json()) for e in log]
    assert replay(start, decoded).model_dump() == state.model_dump()


def test_install_offers_no_side_quest_and_the_first_giver_asks_on_arrival() -> None:
    start, state, log = campaign_state(offered=False)
    assert state.world.quests == {}
    out = settle(state, list(log), log)
    asked = [e for e in out if isinstance(e, QuestAsked)]
    assert [e.ask.quest_id for e in asked] == [LEDGER]  # one ask, the first in plan order
    told = event_line(state, asked[0])  # what the narrator is told
    assert told is not None and told.startswith("Tobin Marrow asks the party: ")
    assert told.endswith("invent no other quest.")
    assert template_line(state, asked[0]) == "Tobin Marrow asks for help: The Missing Ledger."
    ledger = state.world.quests[LEDGER]
    assert ledger.state is QuestState.OFFERED and ledger.objective
    assert [s.kind for s in ledger.steps] == [StepKind.CLEAR, StepKind.MEET]
    assert CHOIR not in state.world.quests  # its giver is here too: asked on a later arrival
    assert state.world.leads == []  # both act-1 givers live at the arrival
    assert state.world.quest_ask is not None and state.world.quest_ask.quest_id == LEDGER
    _replays(start, state, log)


def test_accept_makes_the_quest_active_and_closes_the_card() -> None:
    start, state, log = fresh()
    accept(state, LEDGER, log)
    assert state.world.quests[LEDGER].state is QuestState.ACTIVE
    assert state.world.quest_ask is None
    with pytest.raises(QuestOfferRefused):
        answer_events(state, LEDGER, True)
    _replays(start, state, log)


def test_not_now_keeps_it_offered_and_the_giver_asks_again_next_arrival() -> None:
    start, state, log = fresh()
    declined = apply_all(state, answer_events(state, LEDGER, False), log)
    assert declined == [QuestAskDeclined(quest_id=LEDGER)]
    assert state.world.quest_ask is None
    assert state.world.quests[LEDGER].state is QuestState.OFFERED
    assert settle(state, [], log) == []  # no arrival, no ask
    go(state, R1.spokes[0].id, log)
    if state.campaign is not None and state.campaign.offer is not None:
        fight_won(state, log)
    out = go(state, R1.arrival.id, log)
    asked = [e.ask.quest_id for e in out if isinstance(e, QuestAsked)]
    assert asked == [LEDGER]
    assert not [e for e in out if isinstance(e, QuestUpdated) and e.quest.id == LEDGER]
    _replays(start, state, log)


def test_leaving_the_node_withdraws_the_card() -> None:
    _, state, log = fresh()
    apply_all(state, [_moved(state, R1.spokes[1].id)], log)
    assert state.world.quest_ask is None
    assert state.world.quests[LEDGER].state is QuestState.OFFERED


def _moved(state: GameState, node: str) -> PartyMoved:
    world = state.world
    return PartyMoved(from_node=world.current_node, to_node=node, scene_index=world.scene_index + 1)


def test_no_card_while_an_encounter_offer_waits() -> None:
    _, state, log = campaign_state(offered=False)
    spoke = R1.spokes[0].id
    moved = move(state, spoke, log)
    assert state.campaign is not None and state.campaign.offer is not None
    state.world.npcs["tobin-marrow"].node_id = spoke  # the giver happens to stand there
    batch = [_moved_to_here(state), *moved]
    assert ask_events(state, batch) == []


def _moved_to_here(state: GameState) -> PartyMoved:
    node = state.world.current_node
    assert node is not None
    return PartyMoved(from_node=None, to_node=node, scene_index=state.world.scene_index)


def test_crossing_asks_first_then_leaves_open_tasks_behind() -> None:
    start, state, log = fresh()
    accept(state, LEDGER, log)
    resolve_region_one(state, log)
    assert state.world.quests[LEDGER].state is QuestState.COMPLETED  # done on the way
    assert state.world.quests[CHOIR].state is QuestState.OFFERED  # asked, never answered
    cross = crossing(state, R2.arrival.id)
    assert cross is not None and [q.id for q in cross.quests] == [CHOIR]
    assert crossing_prompt(cross) == (
        f"Crossing into {R2.name} leaves these behind: Break the Smugglers. Go on?"
    )
    call = tool_call("move_party", node_id=R2.arrival.id)
    held = execute_tool(state, call, ToolContext("fighter"), random.Random(1), REGS)
    assert held.pending is not None and not held.events
    assert held.pending.prompt == crossing_prompt(cross)
    sure = ToolContext("fighter", confirm_hostile=True)
    result = execute_tool(state, call, sure, random.Random(1), REGS)
    assert result.ok
    out = settle(state, apply_all(state, list(result.events), log), log)
    choir = state.world.quests[CHOIR]
    assert choir.state is QuestState.FAILED and choir.closed_reason is ClosedReason.LEFT_BEHIND
    assert choir.log[-1] == f"Left behind on leaving {R1.name}."
    closed = _closed_event(out)
    assert template_line(state, closed) == "Break the Smugglers is left behind, unfinished."
    assert event_line(state, closed) == (
        "Quest 'Break the Smugglers' was left behind unfinished (no penalty)."
    )
    assert state.world.quests[LEDGER].state is QuestState.COMPLETED
    leads = [e.lead for e in out if isinstance(e, QuestLeadAdded)]
    assert [(lead.quest_id, lead.text) for lead in leads] == [
        (SIGNET, "Someone at Thornwood Shrine may need help.")
    ]
    assert event_line(state, QuestLeadAdded(lead=leads[0])) == (
        "A lead for the party: Someone at Thornwood Shrine may need help."
    )
    assert left_behind_events(state) == []  # once
    _replays(start, state, log)


def _closed_event(events: list[AnyEvent]) -> QuestUpdated:
    return next(
        e for e in events if isinstance(e, QuestUpdated) and e.quest.state is QuestState.FAILED
    )


def test_a_task_with_every_step_done_completes_instead_of_being_left_behind() -> None:
    _, state, log = fresh()
    resolve_region_one(state, log)
    done = Quest(
        id="q-own",
        title="Own errand",
        giver_npc_id="tobin-marrow",
        state=QuestState.ACTIVE,
        steps=plan().quests[0].steps[:1],
    )
    apply_all(state, [QuestUpdated(quest=done)], log)
    cross = crossing(state, R2.arrival.id)
    assert cross is not None and "q-own" not in {q.id for q in cross.quests}
    settle(state, [], log)
    assert state.world.quests["q-own"].state is QuestState.COMPLETED


def test_the_lead_goes_once_the_giver_asks() -> None:
    start, state, log = fresh()
    resolve_region_one(state, log)
    go(state, R2.arrival.id, log)
    assert [lead.quest_id for lead in state.world.leads] == [SIGNET]
    assert lead_events(state) == []
    shrine = R2.spokes[0].id  # Thornwood Shrine, the giver's place
    go(state, shrine, log)
    if state.campaign is not None and state.campaign.offer is not None:
        assert state.world.quest_ask is None  # never two cards at once
        fight_won(state, log)
        go(state, R2.arrival.id, log)
        go(state, shrine, log)
    assert state.world.quest_ask is not None and state.world.quest_ask.quest_id == SIGNET
    assert state.world.leads == []
    _replays(start, state, log)


def test_v1_slendee_old_save_leaves_act_one_behind_and_asks_again_in_act_two() -> None:
    start, state, log, plan_ = slendee_in_act_two()
    out = settle(state, log[-1:], log)
    quests = state.world.quests
    act1 = [q.id for q in plan_.quests if q.act == 1]
    assert len(act1) == 3
    for quest_id in act1:
        assert quests[quest_id].closed_reason is ClosedReason.LEFT_BEHIND
    asked = [e.ask.quest_id for e in out if isinstance(e, QuestAsked)]
    assert asked == ["the-man-in-the-runnel"]  # old-carrion-vess stands at the arrival
    assert quests["roots-over-water"].state is QuestState.OFFERED
    accept(state, "the-man-in-the-runnel", log)
    runnel = state.world.quests["the-man-in-the-runnel"]
    assert runnel.state is QuestState.ACTIVE
    assert [s.kind for s in runnel.steps] == [StepKind.FREE, StepKind.MEET]  # derived on accept
    assert runnel.objective
    assert left_behind_events(state) == []
    _replays(start, state, log)


def test_reducer_keeps_one_card_and_refuses_stray_answers() -> None:
    _, state, _ = fresh()
    ask = state.world.quest_ask
    assert ask is not None
    with pytest.raises(ReducerError):
        apply(state, QuestAsked(ask=ask))  # never two cards at once
    with pytest.raises(ReducerError):
        apply(state, QuestAskDeclined(quest_id=CHOIR))
    with pytest.raises(ReducerError):
        apply(state, QuestLeadRemoved(quest_id=CHOIR))
    stray = QuestAsk(quest_id="nope", npc_id="tobin-marrow", node_id=R1.arrival.id)
    apply(state, QuestAskDeclined(quest_id=LEDGER))
    with pytest.raises(ReducerError):
        apply(state, QuestAsked(ask=stray))  # only an offered quest can be asked
