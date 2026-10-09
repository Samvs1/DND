"""M15.1 (b): after a defeat retry, the next hero turn prompts its connected player and waits."""

from pathlib import Path

from aidm.models.commands import EndTurnCommand
from aidm.models.protocol_client import CombatCommandMsg, DefeatRetry, Hello
from aidm.models.protocol_server import TurnPrompt
from aidm.models.protocol_views import TablePhase
from aidm.session.persistence import CampaignStore
from aidm.session.turn_clock import GRACE_SECONDS
from tests.session.defeat_fixtures import end_turns_until_over, party_of
from tests.session.table_fixtures import (
    drain_queue,
    fake_llm,
    join,
    of_type,
    running,
    screen_seat,
    start_fight,
)


async def test_playtest_retry_prompts_the_player(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    state = party_of("fighter", hp={"fighter": 1})
    llm, _ = fake_llm(tmp_path)
    async with running(llm, state, store=store) as (table, clock):
        await screen_seat(table)
        sam = await join(table, "Sam", "fighter")
        await start_fight(table, "wolf")
        clock.advance(91)
        await table.settle()
        await end_turns_until_over(table, [sam])
        assert table.phase is TablePhase.DEFEATED
        sam.drain()
        sam.send(DefeatRetry())
        await table.settle()
        assert table.phase is TablePhase.PLAY and table.in_combat
        prompts = of_type(sam.drain(), TurnPrompt)
        assert prompts and prompts[-1].creature_id == "fighter"
        assert table.turn_key is not None
        before = table.state.event_count
        clock.advance(5)
        await table.settle()
        assert table.state.event_count == before, "nothing is played for the waiting hero"


async def test_playtest_retry_connection_drop_keeps_the_turn(tmp_path: Path) -> None:
    """The playtest: after the retry every hero turn was prompted and then auto-played at once
    (the phone's connection dropped). A drop now keeps the turn for the reconnect grace."""
    store = CampaignStore(tmp_path / "saves")
    state = party_of("fighter", hp={"fighter": 1})
    llm, _ = fake_llm(tmp_path)
    async with running(llm, state, store=store) as (table, clock):
        sam = await join(table, "Sam", "fighter")
        await start_fight(table, "wolf")
        await end_turns_until_over(table, [sam])
        sam.send(DefeatRetry())
        await table.settle()
        key, before = table.turn_key, table.state.event_count
        assert key is not None
        table.disconnect(sam.conn.id)
        await table.settle()
        clock.advance(GRACE_SECONDS - 1)
        await table.settle()
        assert table.turn_key == key and table.state.event_count == before
        back = table.connect()
        table.submit(back.id, Hello(name="Sam", token=sam.token))
        await table.settle()
        prompts = of_type(drain_queue(back), TurnPrompt)
        assert prompts and prompts[-1].creature_id == "fighter"
        clock.advance(600)
        await table.settle()
        assert table.turn_key == key, "a solo table has no turn timer"
        assert table.state.event_count == before


async def test_playtest_away_owner_gets_the_grace_then_the_safe_turn(tmp_path: Path) -> None:
    state = party_of("fighter", hp={"fighter": 30})
    llm, _ = fake_llm(tmp_path)
    async with running(llm, state) as (table, clock):
        sam = await join(table, "Sam", "fighter")
        await start_fight(table, "wolf")
        enc = table.state.encounter
        assert enc is not None and table.turn_key is not None
        sam.send(CombatCommandMsg(command=EndTurnCommand(actor_id=enc.active_id() or "")))
        table.disconnect(sam.conn.id)
        await table.settle()
        enc = table.state.encounter
        assert table.turn_key is not None, "the next hero turn waits for the grace"
        assert enc is not None and enc.active_id() == "fighter"
        assert not table.players[sam.player_id].connected
        clock.advance(GRACE_SECONDS)
        await table.settle()
        hesitated = [e for e in table.log if getattr(e.event, "reason", "") == "dodge"]
        assert hesitated, "after the grace the careful turn is played"
