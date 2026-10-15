"""M23.5 favours through the settle and the table (FakeLLM): Not now lets a favour go, moving on
withdraws its card and lets it lapse, leaving the region leaves it behind; an offered quest whose
giver lives in a region already left closes as left behind (the Slendee plan)."""

from pathlib import Path
from typing import Any

from aidm.dm.fake_llm import fake_calls
from aidm.models.events import AnyEvent
from aidm.models.protocol_client import AnswerQuestOffer, SubmitAction
from aidm.models.protocol_server import Notice
from aidm.models.quests import QuestKind
from aidm.models.state import GameState
from aidm.models.world import ClosedReason, QuestState
from aidm.rules.favours import open_favour
from aidm.rules.quest_leaving import crossing
from aidm.rules.quest_offers import answer_events
from tests.ai.tool_fixtures import run_tool
from tests.session.progression_fixtures import apply_all
from tests.session.quest_offer_fixtures import (
    R1,
    R2,
    accept,
    fresh,
    go,
    resolve_region_one,
    settle,
    slendee_in_act_two,
)
from tests.session.table_fixtures import assert_replays, fake_llm, join, of_type, running

ASKER = "dessa-orrin"
LEARN: dict[str, Any] = {
    "npc": ASKER,
    "title": "The lamp oath",
    "kind": "learn",
    "text": "Learn the words of the old lamp oath",
    "tag": "obsidian vow",
}


def _ready() -> tuple[GameState, list[AnyEvent]]:
    _, state, log = fresh()
    apply_all(state, answer_events(state, "missing-ledger", False), log)
    return state, log


def _favour(state: GameState, log: list[AnyEvent]) -> None:
    result = run_tool(state, "offer_favour", **LEARN)
    assert result.ok, result.error
    apply_all(state, list(result.events), log)


def test_not_now_lets_a_favour_go_without_a_deed() -> None:
    state, log = _ready()
    _favour(state, log)
    before = state.world.npcs[ASKER].deeds
    apply_all(state, answer_events(state, "favour-1", False), log)
    favour = state.world.quests["favour-1"]
    assert favour.state is QuestState.FAILED and favour.closed_reason is ClosedReason.WITHDRAWN
    assert state.world.quest_ask is None and state.world.npcs[ASKER].deeds == before
    assert open_favour(state) is None
    again = run_tool(state, "offer_favour", **LEARN)  # a let-go favour may be asked again
    assert again.ok and again.events[0].type == "quest_updated"


def test_moving_on_withdraws_the_card_and_the_favour_lapses() -> None:
    state, log = _ready()
    _favour(state, log)
    go(state, R1.spokes[1].id, log)
    favour = state.world.quests["favour-1"]
    assert favour.closed_reason is ClosedReason.WITHDRAWN
    assert open_favour(state) is None


def test_an_open_favour_is_asked_about_at_the_border_and_left_behind() -> None:
    state, log = _ready()
    _favour(state, log)
    accept(state, "favour-1", log)
    resolve_region_one(state, log)
    cross = crossing(state, R2.arrival.id)
    assert cross is not None and "favour-1" in [q.id for q in cross.quests]
    go(state, R2.arrival.id, log)
    favour = state.world.quests["favour-1"]
    assert favour.kind is QuestKind.FAVOUR
    assert favour.state is QuestState.FAILED and favour.closed_reason is ClosedReason.LEFT_BEHIND


def test_v1_slendee_offered_quest_with_its_giver_left_behind_closes() -> None:
    _, state, log, plan_ = slendee_in_act_two()
    penance = next(q for q in plan_.quests if q.id == "the-knight-s-penance")
    assert penance.act == 2 and penance.giver_npc_id == "warden-sellen-ost"
    assert state.world.npcs["warden-sellen-ost"].node_id == plan_.acts[0].region.gateway.id
    settle(state, log[-1:], log)
    knight = state.world.quests["the-knight-s-penance"]
    assert knight.state is QuestState.FAILED and knight.closed_reason is ClosedReason.LEFT_BEHIND
    assert state.world.quests["roots-over-water"].state is QuestState.OFFERED  # giver in act 2


async def test_table_favour_card_not_now_lets_it_go(tmp_path: Path) -> None:
    state, _ = _ready()
    ask = fake_calls([("offer_favour", LEARN)])
    llm, _ = fake_llm(tmp_path, [ask])
    async with running(llm, state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text='"Dessa, is there anything we can do for you?"'))
        await table.settle()
        card = table.snapshot().state.quest_offer
        assert card is not None and card.quest_id == "favour-1" and card.giver == "Dessa Orrin"
        ann.drain()
        ann.send(AnswerQuestOffer(quest_id="favour-1", accept=False))
        await table.settle()
        notes = [m.text for m in of_type(ann.drain(), Notice)]
        assert any("lets the favour go" in text for text in notes)
        assert table.state.world.quests["favour-1"].closed_reason is ClosedReason.WITHDRAWN
        assert_replays(table)
