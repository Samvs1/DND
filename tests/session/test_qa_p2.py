"""Regressions for the P2 table defects of the adversarial QA report (docs/QA_REPORT.md, M9.5)."""

from pathlib import Path

from aidm.models.protocol_client import (
    Hello,
    HostDifficulty,
    HostKick,
    RollAbilities,
    SubmitAction,
)
from aidm.models.protocol_server import AbilityRolls, ErrorCode, ErrorMsg, Notice, Welcome
from aidm.models.state import GameState
from aidm.session.persistence import CampaignStore
from aidm.session.restore import restore
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import (
    disabled_llm,
    drain_queue,
    join,
    join_with_token,
    menu_llm,
    of_type,
    pick,
    running,
)

SEARCH = pick(("search:investigation", [], None))  # "I search behind the hearth" (M36.10a)


async def test_qa_06_second_hello_reuses_the_seat_and_close_leaves_it_away(
    tmp_path: Path,
) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        seats = len(table.players)
        for _ in range(5):
            bob.send(Hello(name="Bob"))
        bob.send(Hello(name="clone"))
        await table.settle()
        assert len(table.players) == seats
        welcomes = of_type(bob.drain(), Welcome)
        assert welcomes and {w.player_id for w in welcomes} == {bob.player_id}
        table.disconnect(bob.conn.id)
        await table.settle()
        assert not table.players[bob.player_id].connected
        assert not any(p.connected for p in table.players.values() if p.name in ("Bob", "clone"))


async def test_qa_06_hello_with_another_token_moves_the_connection(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        bob.send(Hello(name="Ann", token=ann.token))
        await table.settle()
        assert not table.players[bob.player_id].connected
        assert table.player_for(bob.conn.id) is table.players[ann.player_id]


async def test_qa_07_kick_holds_for_the_connection_and_the_name(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        host = await join(table, "Ann", "fighter")
        carol = await join(table, "Carol", "rogue")
        host.send(HostKick(player_id=carol.player_id))
        await table.settle()
        seats = set(table.players)
        carol.drain()
        carol.send(Hello(name="Carol2"))
        await table.settle()
        errors = of_type(carol.drain(), ErrorMsg)
        assert errors and errors[-1].code is ErrorCode.REFUSED
        other = table.connect()
        table.submit(other.id, Hello(name="carol"))
        await table.settle()
        assert of_type(drain_queue(other), ErrorMsg)[-1].code is ErrorCode.REFUSED
        assert set(table.players) == seats
        host.drain()
        newcomer = table.connect()
        table.submit(newcomer.id, Hello(name="Dave"))
        await table.settle()
        assert of_type(drain_queue(newcomer), Welcome)
        assert any("Dave joined" in n.text for n in of_type(host.drain(), Notice))


async def test_qa_09_progress_goes_back_to_the_renamed_save_folder(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    llm = menu_llm(tmp_path, SEARCH)[0]
    async with running(llm, inn_state(), store=store) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I search behind the hearth"))
        await table.settle()
        cid = table.state.campaign_id
    (store.root / cid).rename(store.root / "my-backup")
    loaded = store.load("my-backup")
    async with running(disabled_llm(tmp_path), inn_state(), store=store) as (table, _):
        restore(table, loaded)
        ann = await join_with_token(table, "Ann", loaded.meta.seats[0].token)
        ann.send(HostDifficulty(monster_hp=0.5, monster_damage=1.0))
        await table.settle()
        final = table.state.model_dump()
    assert not (store.root / cid).exists()
    again = store.load("my-backup")
    assert not again.recovered and again.state.model_dump() == final
    assert again.state.difficulty.monster_hp == 0.5


async def test_qa_11_one_ability_roll_per_player(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), GameState(campaign_id="qa11", seed=3)) as (
        table,
        _,
    ):
        ann = await join(table, "Ann")
        for _ in range(5):
            ann.send(RollAbilities())
        await table.settle()
        sets = [tuple(r.total for r in m.rolls) for m in of_type(ann.drain(), AbilityRolls)]
        assert len(sets) == 5 and len(set(sets)) == 1
