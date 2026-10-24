"""M33.1 (docs/reviews/M33_ultrareview.md findings 4 and 7): the road-by-road walk stops where a
giver's card opens, and a line held for a hero's turn is played once, in that turn, or said to
lapse, on the real round-5 states."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from aidm.models.campaign_state import OfferChoice
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import EndTurnCommand
from aidm.models.events import AnyEvent
from aidm.models.protocol_client import AnswerOffer, CombatCommandMsg, SubmitAction
from aidm.models.protocol_server import Notice
from aidm.models.quest_events import QuestAsked
from aidm.models.quests import QuestKind
from aidm.models.state import GameState
from aidm.models.world import QuestAsk, QuestState
from aidm.models.world_events import PartyMoved
from aidm.session import quest_flow, waiting_line
from aidm.session.scene_votes import STOPPED
from aidm.session.table import Table
from aidm.session.turn_clock import GRACE_SECONDS
from tests.session.m32_play import QUESTS, TYPED, typed
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import (
    Seat,
    assert_replays,
    disabled_llm,
    join,
    join_with_token,
    of_type,
    running,
)

CROSS, BARROW = "hollowgate-cross", "barrow-of-the-hollow-king"
ROOK = "pc-p6"
ASKED = "side-asked-at-the-cross"


def _ask_at_the_cross(state: GameState, batch: Sequence[AnyEvent]) -> list[AnyEvent]:
    arrived = any(isinstance(e, PartyMoved) and e.to_node == CROSS for e in batch)
    if not arrived or state.world.quest_ask is not None:
        return []
    return [QuestAsked(ask=QuestAsk(quest_id=ASKED, npc_id="reeve-hallick", node_id=CROSS))]


async def test_v1_m33_road_walk_stops_at_a_quest_ask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 4: the next road withdrew the giver's Accept / Not now card at once."""
    state = replay_until(TYPED, 394)  # "back to Hollowgate Cross, then on to the Barrow"
    quest = state.world.quests["favour-1"].model_copy(
        update={"id": ASKED, "kind": QuestKind.SIDE, "state": QuestState.OFFERED}
    )
    state.world.quests[ASKED] = quest
    monkeypatch.setattr(quest_flow, "ask_events", _ask_at_the_cross)
    actor, text = typed(TYPED, 394)
    async with running(disabled_llm(tmp_path), state) as (table, _):
        seat = await join(table, "Ann", actor)
        seat.drain()
        seat.send(SubmitAction(text=text))
        await table.settle()
        notices = [m.text for m in of_type(seat.drain(), Notice)]
        assert_replays(table)
        moved = [e.event.to_node for e in table.log if isinstance(e.event, PartyMoved)]
        assert moved == [CROSS]
        ask = table.state.world.quest_ask
        assert ask is not None and ask.quest_id == ASKED
    why = "Reeve Hallick asks for your help here"
    stop = STOPPED.format(here="Hollowgate Cross", why=why, goal="Barrow of the Hollow King")
    assert any(n.lower() == stop.lower() for n in notices), notices


async def _rook_turn_away(table: Table) -> tuple[Seat, Seat, str]:
    """Rook's line held, Rook's player gone, the offer answered Fight from the other seat, and
    the turns played until Rook's opens (the other seat ends its own turns)."""
    rook = await join(table, "Ann", ROOK)
    other = await join(table, "Sam", "pc-p2")
    _, text = typed(QUESTS, 162)
    waiting_line.keep(table.players[rook.player_id], text)
    table.disconnect(rook.conn.id)
    await table.settle()
    other.send(AnswerOffer(choice=OfferChoice.FIGHT))
    await table.settle()
    for _ in range(40):
        enc = table.state.encounter
        active = enc.active_id() if enc is not None else None
        if active == ROOK and table.turn_key is not None:
            break
        assert active == "pc-p2", active
        other.send(CombatCommandMsg(command=EndTurnCommand(actor_id="pc-p2")))
        await table.settle()
    held = table.players[rook.player_id].waiting_line
    assert held is not None and held.due == table.turn_key
    return rook, other, text


def _rook_shots(table: Table) -> list[AttackRolled]:
    events = [e.event for e in table.log]
    return [e for e in events if isinstance(e, AttackRolled) and e.attacker_id == ROOK]


async def test_v1_m33_held_line_plays_when_the_player_returns(tmp_path: Path) -> None:
    """Finding 7: a player away as Rook's turn opened lost the attack typed at the offer."""
    async with running(disabled_llm(tmp_path), replay_until(QUESTS, 162)) as (table, _):
        rook, _, _ = await _rook_turn_away(table)
        assert not _rook_shots(table)
        back = await join_with_token(table, "Ann", rook.token)
        await table.settle()
        assert [(e.attack, e.target_id) for e in _rook_shots(table)] == [("Shortbow", "bandit-1")]
        assert table.players[back.player_id].waiting_line is None
        await join_with_token(table, "Ann", rook.token)  # again: never played twice
        await table.settle()
        assert len(_rook_shots(table)) == 1
        assert_replays(table)


async def test_v1_m33_held_line_that_lapses_is_said(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), replay_until(QUESTS, 162)) as (table, clock):
        rook, other, _ = await _rook_turn_away(table)
        other.drain()
        clock.advance(GRACE_SECONDS)
        await table.settle()
        lapsed = waiting_line.LAPSED.format(name="Rook", why="the turn passed first")
        assert lapsed in [m.text for m in of_type(other.drain(), Notice)]
        assert table.players[rook.player_id].waiting_line is None
        assert not _rook_shots(table)


async def test_v1_m33_held_line_at_the_fight_end_is_said(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), replay_until(QUESTS, 162)) as (table, _):
        rook = await join(table, "Ann", ROOK)
        rook.drain()
        waiting_line.keep(table.players[rook.player_id], "I shoot the bandit")
        waiting_line.drop_all(table)
        lapsed = waiting_line.LAPSED.format(name="Rook", why="the fight ended first")
        assert lapsed in [m.text for m in of_type(rook.drain(), Notice)]
        assert table.players[rook.player_id].waiting_line is None
