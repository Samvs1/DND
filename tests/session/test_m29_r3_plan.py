"""M29.9b campaign plan: quests pay only for deeds the engine checked (docs/playtests/
M29_round3.md T3 T14), reproduced on the round-3 saves (tests/session/playtest_saves.py)."""

import random

from aidm.dm.llm_types import ToolCall
from aidm.dm.tool_context import ToolContext, tool_registries
from aidm.dm.tool_exec import execute_tool
from aidm.dm.tools import dm_tool
from aidm.models.campaign import CampaignPlan
from aidm.models.events import AnyEvent, GoldChanged, XpGained
from aidm.models.quest_events import LoreLearned, QuestStepDone
from aidm.models.state import GameState
from aidm.models.world import QuestAsk, QuestState
from aidm.models.world_events import RewardGranted
from aidm.rules.plan_repair import repair_plan
from aidm.rules.quest_offers import answer_events
from aidm.rules.quest_plan import quest_steps
from aidm.session.quest_flow import settle_after
from aidm.session.reducer import apply
from tests.session.playtest_saves import events_of, replay_until

REGS = tool_registries()
PAID = (RewardGranted, XpGained, GoldChanged)


def _apply(state: GameState, events: list[AnyEvent]) -> list[AnyEvent]:
    for event in events:
        apply(state, event)
    return events


def _settle(state: GameState, batch: list[AnyEvent]) -> list[AnyEvent]:
    return settle_after(state, REGS, batch, lambda events: _apply(state, events))


def _replay(state: GameState, run: str, first: int, last: int) -> list[AnyEvent]:
    """Apply the logged events `first`..`last` (both included) on `state`."""
    batch = [e.event for e in events_of(run) if first <= e.seq <= last]
    return _apply(state, batch)


def _repaired(state: GameState) -> CampaignPlan:
    assert state.campaign is not None
    return repair_plan(state.campaign.plan, [])


def _offer_anew(state: GameState, quest_id: str, giver: str) -> None:
    """The quest offered again here with the repaired plan's steps (as the engine writes them
    now), so the acceptance goes through the real path (`answer_events`)."""
    plan = _repaired(state)
    planned = next(q for q in plan.quests if q.id == quest_id)
    quest = state.world.quests[quest_id].model_copy(
        update={"state": QuestState.OFFERED, "steps": quest_steps(plan, planned)}
    )
    state.world.quests[quest_id] = quest
    node = state.world.current_node
    assert node is not None
    state.world.quest_ask = QuestAsk(quest_id=quest_id, npc_id=giver, node_id=node)


def _accept(state: GameState, quest_id: str) -> list[AnyEvent]:
    events = _apply(state, answer_events(state, quest_id, True))
    return [*events, *_settle(state, events)]


def _steps(events: list[AnyEvent], quest_id: str) -> list[QuestStepDone]:
    return [e for e in events if isinstance(e, QuestStepDone) and e.quest_id == quest_id]


def test_m29_accepting_after_the_visits_closes_nothing_drowned_husband() -> None:
    """r3-full 397-403: accepting "The Drowned Husband's Name" closed its three visit steps at
    once (every place was visited before) and paid 50 XP, 25 gp each and Brass Tears."""
    quest_id = "the-drowned-husband-s-name"
    state = replay_until("r3-full", 397)
    assert state.world.quests[quest_id].state is QuestState.OFFERED
    out = _accept(state, quest_id)
    assert state.world.quests[quest_id].state is QuestState.ACTIVE
    assert not _steps(out, quest_id)
    assert not [e for e in out if isinstance(e, PAID)]
    assert state.world.quests[quest_id].steps_done == 0


def test_m29_step_lines_are_the_engines_drowned_husband() -> None:
    plan = _repaired(replay_until("r3-full", 40))
    quest = next(q for q in plan.quests if q.id == "the-drowned-husband-s-name")
    assert [s.text for s in quest.steps] == [
        "Go to Bogmouth Shrine",
        "Go to The Drowned Causeway",
        "Go to Nighman's Barrow",
    ]
    assert "Corin Skell" in quest.objective or "name" in quest.objective  # flavour stays here


def test_m29_presence_at_acceptance_closes_nothing_widow() -> None:
    """r3-full 31-32: accepting "The Widow of the Deep" at Wrenwater Halt closed its learn step
    ("wrenwater": the place's own name) at once. With the repaired steps (learn, then meet the
    giver instead of the master) nothing closes at acceptance: the party must arrive again."""
    quest_id = "the-widow-of-the-deep"
    state = replay_until("r3-full", 31)
    _offer_anew(state, quest_id, "widow-mera-skell")
    texts = [s.text for s in state.world.quests[quest_id].steps]
    assert texts == ["Learn about wrenwater", "Meet Widow Mera Skell"]
    out = _accept(state, quest_id)
    assert not _steps(out, quest_id)
    assert not [e for e in out if isinstance(e, PAID)]


def test_m29_walking_into_the_master_pays_nothing_piper() -> None:
    """r3-full 1649-1650: "Bring Piper to her mother" (a meet with the master) closed on the
    arrival at the Crown Forge and paid 1600 XP and 800 gp each. A side quest never meets a
    master now: the step meets its giver, Old Nettle Rime."""
    quest_id = "the-daughter-of-cinders"
    state = replay_until("r3-full", 1646)
    plan = _repaired(state)
    planned = next(q for q in plan.quests if q.id == quest_id)
    assert [s.text for s in planned.steps] == ["Meet Piper Vask", "Meet Old Nettle Rime"]
    quest = state.world.quests[quest_id]
    state.world.quests[quest_id] = quest.model_copy(update={"steps": planned.steps})
    settled = _settle(state, _replay(state, "r3-full", 1646, 1648))  # move, place, offer
    assert not _steps(settled, quest_id)
    assert not [e for e in settled if isinstance(e, PAID)]
    assert state.world.quests[quest_id].state is QuestState.ACTIVE


def test_m29_the_giver_step_closes_where_the_giver_is_piper() -> None:
    """r3-full 1631-1632: the party led the child back to Cinderstep Gate, where Old Nettle Rime
    waits: that is the deed the repaired step checks."""
    quest_id = "the-daughter-of-cinders"
    state = replay_until("r3-full", 1632)
    plan = _repaired(state)
    steps = next(q for q in plan.quests if q.id == quest_id).steps
    quest = state.world.quests[quest_id]
    assert quest.steps_done == 1
    state.world.quests[quest_id] = quest.model_copy(update={"steps": steps})
    out = _replay(state, "r3-full", 1632, 1632)
    out += _settle(state, out)
    assert [e.log_line for e in _steps(out, quest_id)] == ["Meet Old Nettle Rime"]


def _brand_state(accepted_at: int) -> GameState:
    """r3-casters: "The Last Brand" accepted at `accepted_at` (through the real path, with the
    engine's step lines), then the logged moves up to the Bastion arrival."""
    quest_id = "the-last-brand"
    state = replay_until("r3-casters", accepted_at)
    _offer_anew(state, quest_id, "hal-the-wainwright")
    _accept(state, quest_id)
    return state


def test_m29_brand_steps_read_what_was_checked_casters() -> None:
    """r3-casters 721-747: "mark it with a lit brand" (the brand attempt failed) and "Sister
    Ilka ... at the gallows" (she was at the Bastion) closed and paid. The engine lines say
    what the steps check, and the honest visits after acceptance still count."""
    quest_id = "the-last-brand"
    state = _brand_state(626)
    out = _replay(state, "r3-casters", 627, 742)
    out += _settle(state, out)
    lines = [e.log_line for e in _steps(out, quest_id)]
    assert lines == ["Go to Fogward Gallows and Weeping Bastion", "Meet Sister Ilka Wellmoss"]
    assert not any("brand" in line or "gallows" in line.lower() for line in lines[1:])


def test_m29_a_visit_before_acceptance_never_counts_casters() -> None:
    """The same quest accepted after the Gallows visit (632): the Bastion arrival (734) is not
    enough, so nothing closes and nothing is paid."""
    quest_id = "the-last-brand"
    state = replay_until("r3-casters", 726)
    _offer_anew(state, quest_id, "hal-the-wainwright")
    state.world.quests[quest_id] = state.world.quests[quest_id].model_copy(update={"steps_done": 0})
    _accept(state, quest_id)
    settled = _settle(state, _replay(state, "r3-casters", 726, 742))
    assert not _steps(settled, quest_id)
    assert not [e for e in settled if isinstance(e, PAID)]  # the logged first visits aside


def _give(state: GameState, actor: str, **args: object) -> list[AnyEvent]:
    call = ToolCall(
        "call_0", "give_keepsake", dm_tool("give_keepsake").args_model.model_validate(args)
    )
    result = execute_tool(state, call, ToolContext(actor_id=actor), random.Random(1), REGS)
    assert result.error is None, result.error
    return list(result.events)


def test_m29_the_archivist_note_teaches_its_tag_items() -> None:
    """r3-items 727-783: the spore-ink note was found, held, read and handed over, and the learn
    step "blackpine" never moved, so "The Archivist Is Missing" failed at the act border. A
    found note that tells what the step asks is a clue now: holding it records the lesson, and
    with the repaired steps (the last one meets the giver, Anwen, not the master) the quest is
    done when the party brings the news back to the Frosted Lantern (741)."""
    quest_id = "the-archivist-is-missing"
    state = replay_until("r3-items", 727)
    steps = next(q for q in _repaired(state).quests if q.id == quest_id).steps
    assert [s.text for s in steps] == [
        "Go to Wrenfall Chapel, Blackpine Reach and Rookmere Bridge",
        "Learn about blackpine",
        "Meet Anwen Toft",
    ]
    quest = state.world.quests[quest_id]
    assert quest.steps_done == 1
    state.world.quests[quest_id] = quest.model_copy(update={"steps": steps})
    events = _give(
        state,
        "pc-p4",
        name="Spore-Ink Note",
        description="In the archivist's hand.",
        teaches="blackpine",
    )
    assert [type(e) for e in events][-1] is LoreLearned
    settled = _settle(state, _apply(state, events))
    assert [(e.step, e.log_line) for e in _steps(settled, quest_id)] == [
        (1, "Learn about blackpine")
    ]
    settled = _settle(state, _replay(state, "r3-items", 728, 742))
    assert [e.log_line for e in _steps(settled, quest_id)] == ["Meet Anwen Toft"]
    assert state.world.quests[quest_id].state is QuestState.COMPLETED


def test_m29_a_note_teaches_only_an_open_tag_items() -> None:
    state = replay_until("r3-items", 727)
    call = ToolCall(
        "call_0",
        "give_keepsake",
        dm_tool("give_keepsake").args_model.model_validate(
            {"name": "Odd Note", "teaches": "dragons"}
        ),
    )
    result = execute_tool(state, call, ToolContext(actor_id="pc-p4"), random.Random(1), REGS)
    assert result.error is not None and "blackpine" in result.error and not result.events
