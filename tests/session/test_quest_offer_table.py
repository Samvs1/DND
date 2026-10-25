"""M23.4 at the table (FakeLLM): the giver's card in the snapshot, Not now / Accept through
`answer_quest_offer`, the card coming back on the next arrival, and the crossing question
(travel vote and the model's `move_party`) with the open tasks left behind on yes.
"""

from pathlib import Path

from aidm.dm.fake_llm import fake_calls
from aidm.models.protocol_client import (
    AnswerQuestOffer,
    CancelHostile,
    ConfirmHostile,
    SubmitAction,
)
from aidm.models.protocol_server import (
    ErrorMsg,
    NarrationChunkMsg,
    Notice,
    PendingConfirmationMsg,
)
from aidm.models.state import GameState
from aidm.models.world import ClosedReason, QuestState
from tests.session.quest_offer_fixtures import R1, R2, accept, fresh, resolve_region_one
from tests.session.table_fixtures import (
    assert_replays,
    fake_llm,
    join,
    menu_llm,
    of_type,
    pick,
    running,
)

LEDGER = "missing-ledger"
CHOIR = "douse-the-choir"


def _asked_at_the_docks() -> GameState:
    """Installed and settled: Tobin Marrow asks; the boathouse's encounter was already offered,
    so the party can walk there and back."""
    _, state, _ = fresh()
    assert state.campaign is not None
    state.campaign.offered_nodes.append(R1.spokes[0].id)
    return state


QUAY = "gullmere-quay-docks"


async def test_quest_card_not_now_comes_back_next_arrival_then_accept(tmp_path: Path) -> None:
    look = pick(("look", [], None))  # the chooser's readings (M36.10a)
    there, back = (pick(("travel", [node], None)) for node in ("rotting-boathouse", QUAY))
    llm, _ = menu_llm(tmp_path, look, there, back)
    async with running(llm, _asked_at_the_docks(), interpreter="menu") as (table, _):
        ann = await join(table, "Ann", "fighter")
        card = table.snapshot().state.quest_offer
        assert card is not None and card.quest_id == LEDGER and card.giver == "Tobin Marrow"
        assert card.title == "The Missing Ledger" and card.objective
        ann.send(SubmitAction(text="I look around"))  # a typed action does not answer the card
        await table.settle()
        assert table.snapshot().state.quest_offer is not None
        ann.send(AnswerQuestOffer(quest_id=LEDGER, accept=False))
        await table.settle()
        notes = [m.text for m in of_type(ann.drain(), Notice)]
        assert any("not now" in text for text in notes)
        assert table.snapshot().state.quest_offer is None
        assert table.state.world.quests[LEDGER].state is QuestState.OFFERED
        ann.send(AnswerQuestOffer(quest_id=LEDGER, accept=True))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg)  # nobody is asking any more
        ann.send(SubmitAction(text="I travel to Rotting Boathouse"))
        await table.settle()
        ann.send(SubmitAction(text="I travel to Gullmere Quay"))
        await table.settle()
        card = table.snapshot().state.quest_offer
        assert card is not None and card.quest_id == LEDGER  # the giver asks again
        ann.drain()
        ann.send(AnswerQuestOffer(quest_id=LEDGER, accept=True))
        await table.settle()
        assert table.state.world.quests[LEDGER].state is QuestState.ACTIVE
        assert of_type(ann.drain(), NarrationChunkMsg)  # the acceptance is told
        assert table.snapshot().state.quest_offer is None
        assert_replays(table)


def _at_the_gateway_with_an_open_task() -> GameState:
    _, state, log = fresh()
    accept(state, LEDGER, log)
    resolve_region_one(state, log)
    assert state.world.quests[CHOIR].state is QuestState.OFFERED
    return state


async def test_crossing_asks_first_and_leaves_open_tasks_behind(tmp_path: Path) -> None:
    cross = pick(("travel", ["lamplighters-rest"], None))  # the chooser's reading (M36.10a)
    llm, _ = menu_llm(tmp_path, cross, cross)
    async with running(llm, _at_the_gateway_with_an_open_task(), interpreter="menu") as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I travel to Lamplighters' Rest"))
        await table.settle()
        asks = of_type(ann.drain(), PendingConfirmationMsg)
        assert [m.prompt for m in asks] == [
            f"Crossing into {R2.name} leaves these behind: Break the Smugglers. Go on?"
        ]
        assert table.state.world.current_node == R1.gateway.id
        ann.send(CancelHostile())
        await table.settle()
        told = " ".join(m.text for m in of_type(ann.drain(), NarrationChunkMsg))
        assert "stays on this side of the border" in told
        assert table.state.world.current_node == R1.gateway.id
        ann.send(SubmitAction(text="I travel to Lamplighters' Rest"))
        await table.settle()
        assert of_type(ann.drain(), PendingConfirmationMsg)
        ann.send(ConfirmHostile())
        await table.settle()
        world = table.state.world
        assert world.current_node == R2.arrival.id
        choir = world.quests[CHOIR]
        assert choir.state is QuestState.FAILED and choir.closed_reason is ClosedReason.LEFT_BEHIND
        assert [lead.quest_id for lead in world.leads] == ["wardens-signet"]
        assert_replays(table)


async def test_model_move_across_the_border_asks_without_a_violence_line(tmp_path: Path) -> None:
    cross = fake_calls([("move_party", {"node_id": R2.arrival.id})])
    llm, _ = fake_llm(tmp_path, [cross])
    async with running(llm, _at_the_gateway_with_an_open_task()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="We push on past the vestry into the next land"))
        await table.settle()
        msgs = ann.drain()
        assert of_type(msgs, PendingConfirmationMsg)
        told = " ".join(m.text for m in of_type(msgs, NarrationChunkMsg))
        assert "brink of violence" not in told
        assert table.pending is not None and table.state.world.current_node == R1.gateway.id
        ann.send(ConfirmHostile())
        await table.settle()
        assert table.state.world.current_node == R2.arrival.id
        assert table.state.world.quests[CHOIR].closed_reason is ClosedReason.LEFT_BEHIND
        assert_replays(table)
