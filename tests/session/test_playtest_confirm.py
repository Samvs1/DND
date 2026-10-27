"""M15.1 (a): a pending hostile act is never narrated as done; the question follows the hold."""

from pathlib import Path

from aidm.dm.fake_llm import fake_calls, fake_text
from aidm.models.protocol_client import ConfirmHostile, SubmitAction
from aidm.models.protocol_server import NarrationChunkMsg, PendingConfirmationMsg
from tests.session.table_fixtures import fake_llm, join, of_type, running, types

BLAST = "A crackling beam of violet light leaps from Ann's hand and strikes Mira."


async def test_playtest_pending_act_not_narrated_as_done(tmp_path: Path) -> None:
    attack = fake_calls([("start_encounter", {"against_npcs": ["npc-mira"]})])
    llm, _ = fake_llm(tmp_path, [attack, fake_text(BLAST)])
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I blast Mira with eldritch fire"))
        await table.settle()
        msgs = ann.drain()
        told = " ".join(m.text for m in of_type(msgs, NarrationChunkMsg))
        assert "violet" not in told
        assert "brink of violence" in told
        kinds = types(msgs)
        last_done = max(i for i, k in enumerate(kinds) if k == "narration_done")
        assert kinds.index("pending_confirmation") > last_done
        assert table.pending is not None and table.state.encounter is None
        ann.send(ConfirmHostile())
        await table.settle()
        assert table.state.encounter is not None


async def test_m43_new_action_leaves_the_pending_act_waiting(tmp_path: Path) -> None:
    """M43.2 B5 (it dropped the card before): a new line plays as itself, the card waits."""
    attack = fake_calls([("start_encounter", {"against_npcs": ["npc-mira"]})])
    llm, _ = fake_llm(tmp_path, [attack])
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I attack Mira"))
        await table.settle()
        assert of_type(ann.drain(), PendingConfirmationMsg)
        ann.send(SubmitAction(text="I look around the room"))
        await table.settle()
        assert table.pending is not None and table.state.encounter is None
