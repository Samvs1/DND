"""The Scribe answers a revive in voice, the host skips him, the UI reads his lines (M13.2)."""

from pathlib import Path

from starlette.testclient import TestClient

from aidm.data.scribe_lines import scribe_lines
from aidm.models.events import CreatureDied, GoldChanged, HpChanged
from aidm.models.protocol_client import ScribeRevive, ScribeSkip
from aidm.models.protocol_server import ErrorCode, ErrorMsg, ScribeLineMsg, ScribeSkipMsg
from aidm.models.state import GameState
from aidm.session.reducer import apply
from tests.ai.guard_fixtures import inn_state
from tests.asset_helpers import expected_audio_url
from tests.session.server_fixtures import make_app
from tests.session.table_fixtures import (
    Seat,
    assert_replays,
    disabled_llm,
    join,
    of_type,
    running,
    screen_seat,
    start_fight,
)


def _state(gold: int, dead: tuple[str, ...] = ("rogue",)) -> GameState:
    state = inn_state()
    for cid in ("fighter", "rogue", "wizard", "cleric"):
        apply(state, GoldChanged(creature_id=cid, delta=gold, gold=gold))
    for cid in dead:
        hp = state.creatures[cid].hp
        apply(state, HpChanged(creature_id=cid, delta=-hp, new_hp=0))
        apply(state, CreatureDied(creature_id=cid))
    return state


def _lines(seat: Seat) -> list[tuple[str, str | None]]:
    return [(m.group, m.to_player_id) for m in of_type(seat.drain(), ScribeLineMsg)]


async def _ask(seat: Seat, target: str) -> None:
    seat.send(ScribeRevive(target_id=target))
    await seat.table.settle()


async def test_refusals_are_addressed_to_the_requester(tmp_path: Path) -> None:
    state = _state(gold=10)
    hp = state.creatures["wizard"].hp
    apply(state, HpChanged(creature_id="wizard", delta=-hp, new_hp=0))
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        screen = await screen_seat(table)
        for seat in (ann, bob, screen):
            seat.drain()
        await _ask(ann, "rogue")
        assert _lines(screen) == [("refuse_funds", ann.player_id)]
        assert _lines(bob) == [("refuse_funds", ann.player_id)]
        await _ask(ann, "wizard")
        assert _lines(ann) == [("refuse_funds", ann.player_id), ("not_yet", ann.player_id)]
        await _ask(bob, "rogue")
        await _ask(ann, "nobody")
        assert _lines(screen) == [("not_yet", ann.player_id)]
        assert of_type(screen.drain(), ErrorMsg) == []
        assert_replays(table)


async def test_combat_and_nobody_fallen_refusals_have_lines(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), _state(gold=100, dead=())) as (table, _):
        ann = await join(table, "Ann", "fighter")
        await _ask(ann, "rogue")
        assert _lines(ann) == [("none_fallen", ann.player_id)]
    async with running(disabled_llm(tmp_path), _state(gold=100)) as (table, _):
        ann = await join(table, "Ann", "fighter")
        await start_fight(table, "wolf")
        ann.drain()
        await _ask(ann, "rogue")
        assert _lines(ann) == [("refuse_combat", ann.player_id)]


async def test_revive_is_heard_by_everyone_and_leaves_the_dice_alone(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), _state(gold=100)) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "wizard")
        screen = await screen_seat(table)
        for seat in (ann, bob, screen):
            seat.drain()
        dice = table.rng.getstate()
        await _ask(ann, "rogue")
        assert not table.state.creatures["rogue"].dead
        for seat in (ann, bob, screen):
            msgs = of_type(seat.drain(), ScribeLineMsg)
            assert [(m.group, m.to_player_id) for m in msgs] == [("revive", None)]
            assert msgs[0].line_id.startswith("revive.")
        assert table.rng.getstate() == dice
        assert_replays(table)


async def test_skip_is_host_only_and_names_the_current_line(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), _state(gold=100)) as (table, _):
        host = await join(table, "Ann", "fighter")
        guest = await join(table, "Bob", "wizard")
        screen = await screen_seat(table)
        await _ask(host, "rogue")
        line = of_type(screen.drain(), ScribeLineMsg)[0].line_id
        guest.drain()
        count = table.state.event_count
        guest.send(ScribeSkip())
        await table.settle()
        error = of_type(guest.drain(), ErrorMsg)
        assert [(e.code, e.refusal) for e in error] == [
            (ErrorCode.NOT_HOST, "scribe_skip_host_only")
        ]
        assert of_type(screen.drain(), ScribeSkipMsg) == []
        host.send(ScribeSkip())
        await table.settle()
        for seat in (host, guest, screen):
            assert [m.line_id for m in of_type(seat.drain(), ScribeSkipMsg)] == [line]
        host.send(ScribeSkip())
        await table.settle()
        assert [m.line_id for m in of_type(screen.drain(), ScribeSkipMsg)] == [None]
        assert table.state.event_count == count


def test_lines_endpoint_lists_every_line(tmp_path: Path) -> None:
    with TestClient(make_app(tmp_path)) as client:
        response = client.get("/api/scribe/lines")
    assert response.status_code == 200
    body = response.json()
    assert [row["id"] for row in body] == [line.id for line in scribe_lines().lines]
    assert all(set(row) == {"id", "group", "text", "audio_url"} for row in body)
    assert all(row["audio_url"] == expected_audio_url(row["id"]) for row in body)
    assert "reference_id" not in response.text
