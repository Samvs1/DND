"""M29.5c G11 (p6 104-108): attacking a friendly NPC printed only "stands on the brink of
violence" with no reason; the hold line now says why the table must confirm."""

from pathlib import Path

from aidm.dm.fake_llm import fake_calls
from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import NarrationChunkMsg, PendingConfirmationMsg
from tests.session.table_fixtures import fake_llm, join, of_type, running


async def test_m29_hold_line_says_why(tmp_path: Path) -> None:
    attack = fake_calls([("start_encounter", {"against_npcs": ["npc-mira"]})])
    llm, _ = fake_llm(tmp_path, [attack])
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I draw my sword and attack Mira without warning"))
        await table.settle()
        msgs = ann.drain()
        told = " ".join(m.text for m in of_type(msgs, NarrationChunkMsg))
        assert "brink of violence" in told and "point of no return" in told
        assert of_type(msgs, PendingConfirmationMsg)
        assert table.state.encounter is None
