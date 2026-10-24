"""M23.5 engine-owned quests through the DM tools: `update_quest` only records a free step,
`offer_favour` registers one typed favour of a present NPC (refusals, the one-open cap) and a
favour pays goodwill only (never XP, gold or items)."""

from typing import Any

import pytest
from pydantic import ValidationError

from aidm.dm.event_text import event_line
from aidm.dm.narration_templates import template_line
from aidm.dm.tools import OfferFavourArgs
from aidm.models.character import Keepsake
from aidm.models.events import AnyEvent, GoldChanged, InventoryChanged, XpGained
from aidm.models.quest_events import QuestAsked, QuestStepDone, RouteDiscovered
from aidm.models.quests import QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.models.world_events import AttitudeChanged, QuestUpdated, RewardGranted
from aidm.rules.dm_tiers import deed_points
from aidm.rules.quest_free import ENGINE_STEPS
from aidm.rules.quest_offers import answer_events
from aidm.rules.quest_rewards import quest_payout, quest_reward_events
from aidm.rules.social_deeds import FAVOUR_DEED_TIER, quest_deed_events
from tests.ai.tool_fixtures import REGS, run_tool
from tests.session.progression_fixtures import apply_all
from tests.session.quest_offer_fixtures import accept, fresh, settle, slendee_in_act_two

ASKER = "dessa-orrin"  # stands at the act-1 arrival, gives no plan quest
SPOKE = "rotting-boathouse"
VISIT: dict[str, Any] = {
    "npc": ASKER,
    "title": "Check the boathouse",
    "kind": "visit",
    "text": "Look in on the rotting boathouse",
    "place": SPOKE,
}


def _ready() -> tuple[GameState, list[AnyEvent]]:
    """The sample act 1 at the arrival, Tobin's card answered Not now (no card open)."""
    _, state, log = fresh()
    apply_all(state, answer_events(state, "missing-ledger", False), log)
    return state, log


def _back_at_the_asker(state: GameState) -> None:
    """M31.1b V14: the party came back to the asker after accepting (the report step)."""
    here = state.world.current_node
    assert here is not None and state.world.npcs[ASKER].node_id == here
    state.world.arrived[here] = state.event_count + 1


def test_m31_a_favour_visit_goes_where_its_words_say() -> None:
    """M31.1b V15: a visit of the party's own place (or a place its words do not name) goes to
    the place the favour's words name; with none left it is the report to the asker alone."""
    state, _ = _ready()
    here = run_tool(state, "offer_favour", **{**VISIT, "place": "gullmere-quay-docks"})
    assert here.error is None, here.error
    favour = next(e for e in here.events if isinstance(e, QuestUpdated)).quest
    assert [(s.kind, s.nodes, s.npc) for s in favour.steps] == [
        (StepKind.VISIT, (SPOKE,), None),
        (StepKind.MEET, (), ASKER),
    ]
    words = {
        **VISIT,
        "title": "Watch the quay",
        "text": "Look around the quay docks",
        "place": "heron-marsh-causeway",
    }
    alone = run_tool(state, "offer_favour", **words)
    assert alone.error is None, alone.error
    favour = next(e for e in alone.events if isinstance(e, QuestUpdated)).quest
    assert [(s.kind, s.npc) for s in favour.steps] == [(StepKind.MEET, ASKER)]


def _favour(state: GameState, log: list[AnyEvent], **args: Any) -> list[AnyEvent]:
    result = run_tool(state, "offer_favour", **{**VISIT, **args})
    assert result.error is None, result.error
    return apply_all(state, list(result.events), log)


def test_a_favour_is_asked_through_the_quest_card() -> None:
    state, log = _ready()
    events = _favour(state, log)
    assert [type(e) for e in events] == [QuestUpdated, QuestAsked]
    favour = state.world.quests["favour-1"]
    assert favour.kind is QuestKind.FAVOUR and favour.state is QuestState.OFFERED
    assert favour.giver_npc_id == ASKER and favour.objective == VISIT["text"]
    # M31.1b V14: a favour ends with a report to the asker
    assert [s.kind for s in favour.steps] == [StepKind.VISIT, StepKind.MEET]
    assert favour.steps[0].text == "Go to Rotting Boathouse"  # M29.9b T3: the engine's line
    assert (favour.steps[1].npc, favour.steps[1].text) == (ASKER, "Meet Dessa Orrin")
    assert state.world.quest_ask is not None and state.world.quest_ask.quest_id == "favour-1"


@pytest.mark.parametrize(
    ("args", "why"),
    [
        ({"npc": "wren-calloway"}, "not here"),  # at a spoke
        ({"npc": "nobody"}, "unknown"),
        ({"place": "harrowmere-bridge"}, "not a place of this region"),  # act 2
        ({"kind": "clear", "place": "gullmere-quay-docks"}, "arrival"),
        ({"kind": "meet", "place": None, "target_npc": ASKER}, "other than the asker"),
        ({"kind": "meet", "place": None, "target_npc": "tobin-marrow"}, "already done"),
        ({"kind": "meet", "place": None, "target_npc": "fenwick-dray"}, "not in this region"),
        (
            {"kind": "deliver", "place": None, "item": "Old map", "target_npc": "wren-calloway"},
            "keepsake a hero carries",
        ),
        ({"kind": "learn", "place": None}, "exactly: tag"),
        ({"kind": "visit", "place": None}, "exactly: place"),
    ],
)
def test_favour_refusals(args: dict[str, Any], why: str) -> None:
    state, _ = _ready()
    result = run_tool(state, "offer_favour", **{**VISIT, **args})
    assert result.error is not None and why in result.error, result.error
    assert not result.events


def test_no_free_or_obtain_favour_in_the_schema() -> None:
    for kind in ("free", "obtain"):
        with pytest.raises(ValidationError):
            OfferFavourArgs.model_validate({**VISIT, "kind": kind})


def test_refused_while_a_card_is_open_or_a_hostile_or_boss_asks() -> None:
    _, state, _ = fresh()  # Tobin's card is open
    waiting = run_tool(state, "offer_favour", **VISIT)
    assert waiting.error is not None and "waiting for the players" in waiting.error
    state, _ = _ready()
    state.world.npcs[ASKER].hostile = True
    assert run_tool(state, "offer_favour", **VISIT).error
    boss = state.world.npcs["boss-gullmere-quay"]
    boss.node_id = state.world.current_node  # even a boss standing here
    refused = run_tool(state, "offer_favour", **{**VISIT, "npc": boss.id})
    assert refused.error is not None and "asks no favours" in refused.error


def test_one_open_favour_at_a_time_and_one_per_npc() -> None:
    state, log = _ready()
    _favour(state, log)
    apply_all(state, answer_events(state, "favour-1", True), log)
    other = {**VISIT, "npc": "odalys-prend", "place": "heron-marsh-causeway"}
    capped = run_tool(state, "offer_favour", **other)
    assert capped.error is not None and "one favour at a time" in capped.error
    state.world.quests["favour-1"] = state.world.quests["favour-1"].model_copy(
        update={"state": QuestState.COMPLETED}
    )
    again = run_tool(state, "offer_favour", **{**VISIT, "place": "heron-marsh-causeway"})
    assert again.error is not None and "already asked" in again.error
    assert run_tool(state, "offer_favour", **other).ok


def test_a_favour_delivers_a_carried_keepsake_never_a_quest_item() -> None:
    state, log = _ready()
    pc = state.creatures["fighter"].pc
    assert pc is not None
    pc.keepsakes.append(Keepsake(id="k-ring", name="Tin ring", quest_id="missing-ledger"))
    deliver = {"kind": "deliver", "place": None, "item": "Tin ring", "target_npc": "wren-calloway"}
    assert run_tool(state, "offer_favour", **{**VISIT, **deliver}).error
    pc.keepsakes[0] = Keepsake(id="k-ring", name="Tin ring")
    assert run_tool(state, "offer_favour", **{**VISIT, **deliver}).ok


def test_a_done_favour_pays_goodwill_only() -> None:
    state, log = _ready()
    _favour(state, log)
    accept(state, "favour-1", log)
    before = state.world.npcs[ASKER].deeds
    state.world.arrived[SPOKE] = state.event_count  # done (a move would also roll an offer)
    _back_at_the_asker(state)
    out = settle(state, [], log)
    assert state.world.quests["favour-1"].state is QuestState.COMPLETED
    paid = (XpGained, GoldChanged, RewardGranted, InventoryChanged)
    assert not [e for e in out if isinstance(e, paid)]
    deeds = [e for e in out if isinstance(e, AttitudeChanged)]
    assert [e.npc_id for e in deeds] == [ASKER]
    assert state.world.npcs[ASKER].deeds == before + deed_points(REGS.tiers, FAVOUR_DEED_TIER)


def test_a_favour_never_pays_even_with_a_plan_quest_id() -> None:
    state, _ = _ready()
    step = QuestStep(kind=StepKind.MEET, text="Meet Wren", npc="wren-calloway")
    done = Quest(
        id="missing-ledger",
        title="Sneaky",
        state=QuestState.COMPLETED,
        kind=QuestKind.FAVOUR,
        giver_npc_id="tobin-marrow",
        steps=(step,),
        steps_done=1,
    )
    assert quest_payout(state, done, REGS.tiers) is None
    assert quest_reward_events(state, done, REGS.tiers, REGS.catalogue) == []
    failed = done.model_copy(update={"state": QuestState.FAILED})
    assert quest_deed_events(state, failed, REGS.tiers) == []  # letting one go costs nothing


def test_update_quest_only_records_a_free_step() -> None:
    _, state, log = fresh()
    accept(state, "missing-ledger", log)
    typed = run_tool(state, "update_quest", quest_id="missing-ledger")
    assert typed.error == ENGINE_STEPS
    main = run_tool(state, "update_quest", quest_id="main-gullmere-quay")
    assert main.error == ENGINE_STEPS  # Force and Peace steps are all typed
    _, old, old_log, _ = slendee_in_act_two()
    settle(old, old_log[-1:], old_log)
    accept(old, "the-man-in-the-runnel", old_log)
    done = run_tool(old, "update_quest", quest_id="the-man-in-the-runnel", reason="found him")
    assert [type(e) for e in done.events] == [QuestStepDone]
    apply_all(old, list(done.events), old_log)
    assert old.world.quests["the-man-in-the-runnel"].steps_done == 1
    assert run_tool(old, "update_quest", quest_id="the-man-in-the-runnel").error == ENGINE_STEPS


def test_update_quest_finishes_an_old_plans_free_peace_route() -> None:
    _, state, log, _ = slendee_in_act_two()
    settle(state, log[-1:], log)
    main = "main-gloomfen-wetlands"
    assert state.world.quests[main].route("peace") is None
    named = run_tool(state, "update_quest", quest_id=main, route_id="peace")
    assert [type(e) for e in named.events] == [RouteDiscovered, QuestStepDone]
    assert run_tool(state, "update_quest", quest_id=main, route_id="force").error


def test_favour_lines_for_the_model_and_the_players() -> None:
    state, log = _ready()
    events = _favour(state, log)
    asked = events[1]
    told = event_line(state, asked)
    assert told is not None and told.startswith("Dessa Orrin asks the party a favour: Look in")
    assert template_line(state, asked) == "Dessa Orrin asks a favour of you: Check the boathouse."
    assert template_line(state, events[0]) is None  # the ask line says it
    accept(state, "favour-1", log)
    state.world.arrived[SPOKE] = state.event_count  # M29.9b: an arrival after acceptance
    _back_at_the_asker(state)
    done = next(e for e in settle(state, [], log) if isinstance(e, QuestUpdated))
    assert "grateful (no reward)" in (event_line(state, done) or "")
    assert "They will remember it." in (template_line(state, done) or "")
