"""Table actor: the exploration queue and the never-silent rule (M6.2, SPEC 10)."""

from pathlib import Path

from aidm.dm.fake_llm import fake_calls
from aidm.models.protocol_client import HostPause, HostResume, SubmitAction
from aidm.models.protocol_server import (
    DiceRoll,
    ErrorCode,
    ErrorMsg,
    EventMsg,
    NarrationChunkMsg,
    NarrationDone,
    Notice,
    QueueState,
    Resolving,
    Snapshot,
    VoteOpen,
)
from aidm.session.table import FALLBACK_NOTICE
from tests.session.table_fixtures import (
    assert_replays,
    disabled_llm,
    fake_llm,
    join,
    of_type,
    running,
)


async def test_queue_is_fifo_and_one_pending_per_player(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        host = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        host.send(HostPause())
        await table.settle()
        host.send(SubmitAction(text="I search behind the hearth"))
        bob.send(SubmitAction(text="I study the rusted lever"))
        host.send(SubmitAction(text="I hum a tune"))
        await table.settle()
        msgs = host.drain()
        queue = of_type(msgs, QueueState)[-1]
        assert [e.player_id for e in queue.entries] == [host.player_id, bob.player_id]
        refused = of_type(msgs, ErrorMsg)
        assert [e.code for e in refused] == [ErrorCode.ALREADY_QUEUED]
        assert not of_type(msgs, Resolving)
        host.send(HostResume())
        await table.settle()
        resolved = [m.entry.text for m in of_type(host.drain(), Resolving)]
        assert resolved == ["I search behind the hearth", "I study the rusted lever"]
        assert not table.queue and table.resolving is None
        assert_replays(table)


async def test_every_action_ends_in_narration_or_a_notice(tmp_path: Path) -> None:
    texts = [
        "look around",
        "I search behind the hearth for loose stones",
        "",
        "???",
        'I ask Mira "any news from the road?"',
        "inventory",
        "travel to nowhere",
        "x" * 900,
    ]
    async with running(disabled_llm(tmp_path)) as (table, _):
        seat = await join(table, "Ann", "fighter")
        for text in texts:
            seat.drain()
            seat.send(SubmitAction(text=text))
            await table.settle()
            msgs = seat.drain()
            assert of_type(msgs, Resolving), text
            after = msgs[msgs.index(of_type(msgs, Resolving)[0]) :]
            told = of_type(after, NarrationDone) or of_type(after, Notice)
            assert told or of_type(after, VoteOpen), f"silent turn for {text!r}"
            for chunk in of_type(after, NarrationChunkMsg):
                assert chunk.text.strip()
        assert_replays(table)


async def test_model_turn_streams_dice_then_narration_and_snapshot(tmp_path: Path) -> None:
    llm, fake = fake_llm(tmp_path)
    async with running(llm) as (table, _):
        seat = await join(table, "Ann", "fighter")
        seat.send(SubmitAction(text="I look around the common room"))
        await table.settle()
        msgs = seat.drain()
        kinds = [m.type for m in msgs]
        assert "narration_chunk" in kinds and "narration_done" in kinds
        assert kinds.index("resolving") < kinds.index("narration_chunk")
        snap = of_type(msgs, Snapshot)[-1]
        assert snap.seq == table.state.event_count
        assert fake.requests, "the adjudicator and narrator used the fake model"
        assert table.state.memory.narration, "narration was recorded into memory"
        assert_replays(table)


async def test_not_joined_and_wrong_phase_are_typed_errors(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        conn = table.connect()
        table.submit(conn.id, SubmitAction(text="hello?"))
        await table.settle()
        first = conn.outbox.get_nowait()
        assert isinstance(first, ErrorMsg) and first.code is ErrorCode.NOT_JOINED
        seat = await join(table, "Zed")
        seat.send(SubmitAction(text="I wave"))
        await table.settle()
        codes = [m.code for m in of_type(seat.drain(), ErrorMsg)]
        assert codes == [ErrorCode.NO_CHARACTER]


async def test_dice_are_broadcast_before_the_narration(tmp_path: Path) -> None:
    check = {"actor": "fighter", "ability_or_skill": "athletics", "dc_tier": "easy", "reason": "x"}
    llm, _ = fake_llm(tmp_path, [fake_calls([("request_check", check)])])
    async with running(llm) as (table, _):
        seat = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        seat.send(SubmitAction(text="I climb the chimney"))
        await table.settle()
        for msgs in (seat.drain(), bob.drain()):
            kinds = [m.type for m in msgs]
            assert "dice_roll" in kinds and "narration_chunk" in kinds
            assert kinds.index("dice_roll") < kinds.index("narration_chunk")
            dice = of_type(msgs, DiceRoll)[0]
            assert dice.dice.roller_id == "fighter" and dice.dice.target is not None
        assert_replays(table)


async def test_a_rolls_dice_go_out_before_its_result_line(tmp_path: Path) -> None:
    """M26.6: the screen's pacer holds what arrives after a roll until its show has ended, so the
    dice lead: a check's "success" line sent first told the result before the die was thrown."""
    check = {"actor": "fighter", "ability_or_skill": "athletics", "dc_tier": "easy", "reason": "x"}
    llm, _ = fake_llm(tmp_path, [fake_calls([("request_check", check)])])
    async with running(llm) as (table, _):
        seat = await join(table, "Ann", "fighter")
        seat.send(SubmitAction(text="I climb the chimney"))
        await table.settle()
        msgs = seat.drain()
        dice = of_type(msgs, DiceRoll)[0]
        lines = [m for m in of_type(msgs, EventMsg) if m.seq == dice.seq]
        assert lines and lines[0].kind == "check_resolved"
        assert msgs.index(dice) < msgs.index(lines[0])


async def test_a_failing_job_is_answered_in_fiction(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        seat = await join(table, "Ann", "fighter")

        async def broken() -> None:
            raise RuntimeError("boom: secret stack detail")

        table.schedule(broken)
        await table.settle()
        notices = of_type(seat.drain(), Notice)
        assert [n.text for n in notices] == [FALLBACK_NOTICE]
        assert all("boom" not in n.text for n in notices)
        seat.send(SubmitAction(text="look around"))
        await table.settle()
        assert of_type(seat.drain(), NarrationDone), "the table keeps working"
