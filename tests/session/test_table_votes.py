"""Table actor: ready votes for travel, rest and shops (M6.2, SPEC 10)."""

from pathlib import Path

from aidm.models.events import GoldChanged
from aidm.models.protocol_client import HostForceVote, ShopBuy, SubmitAction, Vote
from aidm.models.protocol_server import (
    ErrorCode,
    ErrorMsg,
    NarrationDone,
    ShopStock,
    VoteClosed,
    VoteOpen,
)
from aidm.models.protocol_views import VoteKind
from aidm.session.reducer import apply
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import Seat, assert_replays, disabled_llm, join, of_type, running


async def _propose_travel(host: Seat) -> VoteOpen:
    host.send(SubmitAction(text="travel to the forest"))
    await host.table.settle()
    opened = of_type(host.drain(), VoteOpen)
    assert len(opened) == 1 and opened[0].kind is VoteKind.TRAVEL
    return opened[0]


async def test_solo_travel_passes_at_once(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        seat = await join(table, "Ann", "fighter")
        seat.send(SubmitAction(text="travel to the forest"))
        await table.settle()
        msgs = seat.drain()
        closed = of_type(msgs, VoteClosed)
        assert closed and closed[0].passed
        assert table.state.world.current_node == "forest"
        assert of_type(msgs, NarrationDone)
        assert_replays(table)


async def test_vote_needs_a_majority_and_passes_on_the_second_ready(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        host = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        vote = await _propose_travel(host)
        assert set(vote.voters) == {host.player_id, bob.player_id}
        assert table.state.world.current_node == "town"
        bob.send(Vote(vote_id=vote.vote_id, ready=True))
        await table.settle()
        assert of_type(bob.drain(), VoteClosed)[0].passed
        assert table.state.world.current_node == "forest"
        assert_replays(table)


async def test_declined_vote_fails_and_nothing_moves(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        host = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        vote = await _propose_travel(host)
        bob.send(Vote(vote_id=vote.vote_id, ready=False))
        await table.settle()
        closed = of_type(host.drain(), VoteClosed)
        assert closed and not closed[0].passed
        assert table.state.world.current_node == "town" and table.vote is None


async def test_host_can_force_a_vote(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        host = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await join(table, "Cy", "wizard")
        vote = await _propose_travel(host)
        bob.send(HostForceVote())
        await table.settle()
        assert of_type(bob.drain(), ErrorMsg)[0].code is ErrorCode.NOT_HOST
        host.send(HostForceVote())
        await table.settle()
        closed = of_type(host.drain(), VoteClosed)
        assert closed[0].vote_id == vote.vote_id and closed[0].passed
        assert table.state.world.current_node == "forest"


async def test_vote_timeout_passes_when_nobody_declined(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, clock):
        host = await join(table, "Ann", "fighter")
        await join(table, "Bob", "rogue")
        await _propose_travel(host)
        clock.advance(29.0)
        await table.settle()
        assert table.vote is not None
        clock.advance(1.0)
        await table.settle()
        closed = of_type(host.drain(), VoteClosed)
        assert closed and closed[0].passed and closed[0].reason == "time is up"
        assert table.state.world.current_node == "forest"


async def test_disconnected_voter_is_dropped(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        host = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await _propose_travel(host)
        table.disconnect(bob.conn.id)
        await table.settle()
        assert table.vote is None and table.state.world.current_node == "forest"


async def test_short_rest_and_shop_go_through_votes_then_trade(tmp_path: Path) -> None:
    state = inn_state()
    state.world.npcs["npc-mira"].role = "merchant"
    apply(state, GoldChanged(creature_id="fighter", delta=500, gold=500))
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", "fighter")
        seat.send(SubmitAction(text="take a short rest"))
        await table.settle()
        assert table.state.short_rests_used == 1
        seat.send(SubmitAction(text="trade with Mira"))
        await table.settle()
        msgs = seat.drain()
        kinds = [v.kind for v in of_type(msgs, VoteOpen)]
        assert kinds == [VoteKind.SHORT_REST, VoteKind.SHOP]
        stock = of_type(msgs, ShopStock)
        assert stock and stock[0].npc_id == "npc-mira" and stock[0].stock
        assert table.state.world.shop_npc_id == "npc-mira"
        line = stock[0].stock[0]
        seat.send(ShopBuy(npc_id="npc-mira", item_id=line.item_id))
        seat.send(ShopBuy(npc_id="npc-mira", item_id="not-an-item"))
        await table.settle()
        hero = table.state.creatures["fighter"]
        assert hero.pc is not None and hero.pc.gold == 500 - line.price_gp
        refused = of_type(seat.drain(), ErrorMsg)
        assert [e.code for e in refused] == [ErrorCode.REFUSED]
        assert refused[0].refusal == "shop_unknown_item"
        assert_replays(table)
