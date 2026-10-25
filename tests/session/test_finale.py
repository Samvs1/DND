"""M23.9 the finale is a choice: after the final region resolves the phones get the finale card
(derived from state, so it survives a reconnect), nothing ends without the confirm, a confirmed
`choose_finale` tells the ending and runs the campaign-complete path once; a plan without a
finale (old saves) still ends at the final resolution."""

from pathlib import Path

from aidm.models.campaign_events import EpilogueWritten, FinaleChosen
from aidm.models.protocol_client import ChooseFinale, Hello, SubmitAction
from aidm.models.protocol_server import (
    EpilogueMsg,
    ErrorMsg,
    NarrationChunkMsg,
    Notice,
    Snapshot,
)
from aidm.models.protocol_views import TablePhase
from aidm.rules.encounter_offer import arrival_offer_events
from aidm.rules.finale import finale_open
from aidm.rules.progression import campaign_complete
from aidm.rules.quest_hints import FINALE_LINE, what_now
from aidm.session.quest_people import SURE
from aidm.session.reducer import replay
from aidm.session.views_quests import public_finale
from tests.ai.epilogue_fixtures import finished_campaign
from tests.session.progression_fixtures import DATA, apply_all, move, plan
from tests.session.table_fixtures import (
    assert_replays,
    drain_queue,
    join,
    menu_llm,
    of_type,
    pick,
    running,
)

QUESTION = "Silence the Hollow Choir forever, or let its last verse be sung?"
SILENCE, LET = "silence-the-song", "let-it-finish"


def _chosen(table_log: list[object]) -> list[FinaleChosen]:
    return [e for e in table_log if isinstance(e, FinaleChosen)]


def test_final_resolution_opens_the_finale_and_the_story_is_not_over() -> None:
    start, state, log, _ = finished_campaign(ending=None)
    assert state.campaign is not None and state.campaign.complete
    assert not campaign_complete(state)
    card = public_finale(state)
    assert card is not None and QUESTION in card.question and card.chosen is None
    assert [o.id for o in card.options] == [SILENCE, LET]
    assert [o.title for o in card.options] == ["Silence the song", "Let the last verse be sung"]
    assert replay(start, log) == state


def test_no_new_danger_or_offers_while_the_finale_is_open() -> None:
    _, state, log, _ = finished_campaign(ending=None)
    region = plan().acts[2].region
    assert state.campaign is not None
    state.campaign.offered_nodes.clear()  # every place would offer its fight again
    spoke = region.spokes[0].id
    assert move(state, region.arrival.id, log) == []
    assert move(state, spoke, log) == []  # the arrival offer is held back
    finale = plan().finale
    assert finale is not None and what_now(state) == (finale.question, FINALE_LINE)
    chosen = state.model_copy(deep=True)
    apply_all(chosen, [FinaleChosen(option_id=LET)], [])
    assert arrival_offer_events(chosen, DATA, region.arrival.id)  # control: it would come


def test_an_epilogue_written_before_m23_9_keeps_the_save_finished() -> None:
    start, state, log, _ = finished_campaign(ending=None)
    apply_all(state, [EpilogueWritten(text="The tale ended.", source="template")], log)
    assert campaign_complete(state) and finale_open(state) is None
    assert public_finale(state) is None
    assert replay(start, log) == state


def test_a_plan_without_a_finale_ends_at_the_final_resolution() -> None:
    start, state, log, _ = finished_campaign(finale=False)
    assert campaign_complete(state) and finale_open(state) is None
    assert public_finale(state) is None
    assert replay(start, log) == state


async def test_finale_card_confirm_then_ending_and_epilogue_once(tmp_path: Path) -> None:
    _, state, _, _ = finished_campaign(ending=None)
    water = pick(other="")  # the storyteller's line (M36.10a); the AI is otherwise down
    llm = menu_llm(tmp_path, water, storyteller_down=True)[0]
    async with running(llm, state, interpreter="menu") as (table, _):
        ann = await join(table, "Ann", "fighter")
        snap = table.snapshot().state
        assert snap.finale is not None and snap.finale.chosen is None and not snap.complete
        ann.send(SubmitAction(text="We look out over the water"))  # other actions still work
        await table.settle()
        msgs = ann.drain()
        assert of_type(msgs, NarrationChunkMsg) and not of_type(msgs, EpilogueMsg)
        late = table.connect()  # a reconnecting phone gets the card back
        table.submit(late.id, Hello(name="Ann", token=ann.token, last_seq=0))
        await table.settle()
        again = of_type(drain_queue(late), Snapshot)[-1].state
        assert again.finale is not None and again.finale.chosen is None
        ann.send(ChooseFinale(option_id=SILENCE))  # no confirm: nothing final
        await table.settle()
        assert [m.text for m in of_type(ann.drain(), Notice)] == [SURE]
        assert not _chosen([e.event for e in table.log])
        ann.send(ChooseFinale(option_id="burn-it-all", confirm=True))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg) and not _chosen([e.event for e in table.log])
        ann.send(ChooseFinale(option_id=SILENCE, confirm=True))
        await table.settle()
        msgs = ann.drain()
        told = " ".join(m.text for m in of_type(msgs, NarrationChunkMsg))
        assert "Silence the song" in told and "Break the Choir's last hymn" in told
        epilogue = of_type(msgs, EpilogueMsg)
        assert len(epilogue) == 1 and "They chose: Silence the song." in epilogue[0].text
        assert len(_chosen([e.event for e in table.log])) == 1
        snap = table.snapshot().state
        assert snap.complete and snap.epilogue and table.phase is TablePhase.ENDED
        assert snap.finale is not None and snap.finale.chosen == SILENCE
        assert snap.finale.ending.startswith("Break the Choir's last hymn")
        assert_replays(table)


async def test_old_plan_without_a_finale_writes_the_epilogue_as_before(tmp_path: Path) -> None:
    _, state, _, _ = finished_campaign(finale=False)
    toast = pick(other="")  # the storyteller's line (M36.10a); the AI is otherwise down
    llm = menu_llm(tmp_path, toast, storyteller_down=True)[0]
    async with running(llm, state, interpreter="menu") as (table, _):
        ann = await join(table, "Ann", "fighter")
        assert table.snapshot().state.finale is None
        ann.send(SubmitAction(text="We raise a toast"))
        await table.settle()
        msgs = ann.drain()
        assert len(of_type(msgs, EpilogueMsg)) == 1
        ann.send(ChooseFinale(option_id=SILENCE, confirm=True))
        await table.settle()
        assert not of_type(ann.drain(), EpilogueMsg)
        assert table.phase is TablePhase.ENDED
        assert_replays(table)
