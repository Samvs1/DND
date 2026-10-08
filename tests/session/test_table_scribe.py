"""The Scribe's revive over the table actor (M13.1): success, each refusal, replay == snapshot."""

from pathlib import Path

from aidm.models.defeat import PartyDefeated
from aidm.models.events import CreatureDied, GoldChanged, HpChanged
from aidm.models.protocol_client import HostPause, ScribeRevive
from aidm.models.protocol_server import ErrorCode, ErrorMsg, EventMsg, Snapshot
from aidm.models.scribe import ScribeView
from aidm.models.state import GameState
from aidm.session.reducer import apply
from aidm.session.table import Table
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import (
    Seat,
    assert_replays,
    disabled_llm,
    join,
    of_type,
    running,
    start_fight,
)


def _state(gold: int = 100, dead: tuple[str, ...] = ("rogue", "wizard")) -> GameState:
    state = inn_state()
    for cid in ("fighter", "rogue", "wizard", "cleric"):
        apply(state, GoldChanged(creature_id=cid, delta=gold, gold=gold))
    for cid in dead:
        hp = state.creatures[cid].hp
        apply(state, HpChanged(creature_id=cid, delta=-hp, new_hp=0))
        apply(state, CreatureDied(creature_id=cid))
    return state


def _scribe(table: Table, seat: Seat) -> ScribeView:
    seat.drain()
    table.broadcast_snapshot()
    return of_type(seat.drain(), Snapshot)[-1].state.scribe


async def _refusal(table: Table, seat: Seat, target: str) -> ErrorMsg:
    count = table.state.event_count
    seat.send(ScribeRevive(target_id=target))
    await table.settle()
    errors = of_type(seat.drain(), ErrorMsg)
    assert len(errors) == 1 and table.state.event_count == count
    return errors[0]


async def test_revive_round_trip_picks_target_and_replays(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), _state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        snap = _scribe(table, ann)
        assert snap.available and [f.creature_id for f in snap.fallen] == ["rogue", "wizard"]
        assert {f.price_gp for f in snap.fallen} == {25}
        ann.send(ScribeRevive(target_id="wizard"))
        await table.settle()
        wizard = table.state.creatures["wizard"]
        assert not wizard.dead and wizard.hp == -(-wizard.max_hp // 2)
        assert table.state.creatures["rogue"].dead
        fighter = table.state.creatures["fighter"].pc
        assert fighter is not None and fighter.gold == 75
        msgs = ann.drain()
        lines = [m.line for m in of_type(msgs, EventMsg) if m.kind == "character_rewritten"]
        assert lines == ["The Scribe rewrites Celes into the story."]
        after = of_type(msgs, Snapshot)[-1].state.scribe
        assert [f.creature_id for f in after.fallen] == ["rogue"]
        assert_replays(table)


async def test_revive_refusals_spend_nothing(tmp_path: Path) -> None:
    state = _state(gold=10, dead=("rogue",))
    hp = state.creatures["wizard"].hp
    apply(state, HpChanged(creature_id="wizard", delta=-hp, new_hp=0))
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        ann.drain()
        assert (await _refusal(table, ann, "rogue")).refusal == "scribe_no_funds"
        assert (await _refusal(table, ann, "wizard")).refusal == "scribe_not_fallen"
        assert (await _refusal(table, bob, "rogue")).refusal == "scribe_payer_down"
        unknown = await _refusal(table, ann, "nobody")
        assert (unknown.code, unknown.refusal) == (
            ErrorCode.UNKNOWN_TARGET,
            "scribe_unknown_target",
        )
        assert_replays(table)


async def test_revive_refused_when_nobody_fallen(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), _state(dead=())) as (table, _):
        ann = await join(table, "Ann", "fighter")
        snap = _scribe(table, ann)
        assert not snap.available and snap.reason == "scribe_none_fallen"
        error = await _refusal(table, ann, "rogue")
        assert (error.code, error.refusal) == (ErrorCode.REFUSED, "scribe_none_fallen")


async def test_revive_refused_in_combat(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), _state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        await start_fight(table, "wolf")
        ann.drain()
        assert (await _refusal(table, ann, "rogue")).refusal == "scribe_in_combat"
        snap = _scribe(table, ann)
        assert not snap.available and snap.reason == "scribe_in_combat"


async def test_revive_refused_while_paused(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), _state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(HostPause())
        await table.settle()
        ann.drain()
        assert (await _refusal(table, ann, "rogue")).code is ErrorCode.PAUSED
        snap = _scribe(table, ann)
        assert not snap.available and snap.reason == "scribe_paused"


async def test_revive_refused_while_defeated(tmp_path: Path) -> None:
    state = _state()
    apply(state, PartyDefeated(text="The road ends here."))
    async with running(disabled_llm(tmp_path), state) as (table, _):
        ann = await join(table, "Ann", "fighter")
        snap = _scribe(table, ann)
        assert not snap.available and snap.reason == "scribe_defeated"
        error = await _refusal(table, ann, "rogue")
        assert (error.code, error.refusal) == (ErrorCode.WRONG_PHASE, "defeated")
