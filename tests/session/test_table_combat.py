"""Table actor: combat turn ownership, suggestions, timers, autoplay, a full fight (M6.2)."""

import random
from pathlib import Path

from aidm.models.commands import DodgeCommand, EndTurnCommand
from aidm.models.encounter_events import EncounterEnded
from aidm.models.protocol_client import (
    CombatCommandMsg,
    RequestHitChances,
    SubmitAction,
    Suggestion,
)
from aidm.models.protocol_server import (
    CombatState,
    ErrorCode,
    ErrorMsg,
    HitChances,
    NarrationDone,
    Notice,
    SuggestionRelay,
    TurnPrompt,
)
from aidm.session.combat_runner import ai_command
from aidm.session.table import Table
from aidm.session.views import public_combat
from tests.session.table_fixtures import (
    Seat,
    assert_replays,
    disabled_llm,
    join,
    of_type,
    running,
    start_fight,
)


def _active(table: Table) -> str:
    enc = table.state.encounter
    assert enc is not None
    active = enc.active_id()
    assert active is not None
    return active


def _seat_of(seats: list[Seat], table: Table) -> tuple[Seat, Seat]:
    active = _active(table)
    on = next(s for s in seats if table.players[s.player_id].creature_id == active)
    off = next(s for s in seats if s is not on)
    return on, off


async def _fight(table: Table) -> tuple[Seat, Seat]:
    ann = await join(table, "Ann", "fighter")
    bob = await join(table, "Bob", "rogue")
    await start_fight(table, "goblin", "goblin")
    assert table.in_combat and table.turn_key is not None
    return ann, bob


async def test_only_the_active_player_may_act(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        seats = list(await _fight(table))
        on, off = _seat_of(seats, table)
        prompts = of_type(on.drain(), TurnPrompt)
        assert prompts and prompts[-1].player_id == on.player_id
        before = table.state.event_count
        off_pc = table.players[off.player_id].creature_id or ""
        off.send(CombatCommandMsg(command=DodgeCommand(actor_id=off_pc)))
        off.send(SubmitAction(text="I throw sand"))
        await table.settle()
        codes = [m.code for m in of_type(off.drain(), ErrorMsg)]
        assert codes == [ErrorCode.NOT_YOUR_TURN, ErrorCode.NOT_YOUR_TURN]
        assert table.state.event_count == before
        on.send(CombatCommandMsg(command=DodgeCommand(actor_id=off_pc)))
        await table.settle()
        assert of_type(on.drain(), ErrorMsg)[0].code is ErrorCode.INVALID
        assert table.state.event_count == before


async def test_suggestion_and_hit_chances(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        seats = list(await _fight(table))
        on, off = _seat_of(seats, table)
        off.send(Suggestion(text="hit the left goblin"))
        goblin = next(cid for cid in table.state.creatures if cid.startswith("goblin"))
        on.send(RequestHitChances(target_id=goblin))
        await table.settle()
        msgs = on.drain()
        relay = of_type(msgs, SuggestionRelay)
        assert relay and relay[0].player_id == off.player_id
        chances = of_type(msgs, HitChances)
        assert chances and chances[0].chances and chances[0].target_id == goblin
        assert not of_type(off.drain(), SuggestionRelay)


async def test_turn_timer_plays_a_safe_default(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, clock):
        seats = list(await _fight(table))
        on, _ = _seat_of(seats, table)
        stuck = _active(table)
        key = table.turn_key
        clock.advance(89.0)
        await table.settle()
        assert table.turn_key == key
        clock.advance(1.0)
        await table.settle()
        notices = [n.text for n in of_type(on.drain(), Notice)]
        assert any("hesitates" in t for t in notices)
        enc = table.state.encounter
        assert table.turn_key != key or enc is None or enc.active_id() != stuck
        assert_replays(table)


async def test_disconnect_autoplays_the_turn(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        seats = list(await _fight(table))
        on, off = _seat_of(seats, table)
        key = table.turn_key
        table.disconnect(on.conn.id)
        await table.settle()
        assert table.turn_key != key
        assert any("hesitates" in n.text for n in of_type(off.drain(), Notice))


async def test_full_fight_ends_and_returns_to_exploration(tmp_path: Path) -> None:
    rng = random.Random(4)
    async with running(disabled_llm(tmp_path)) as (table, _):
        seats = list(await _fight(table))
        for _ in range(300):
            if not table.in_combat:
                break
            on, _ = _seat_of(seats, table)
            active = _active(table)
            command = ai_command(table.state, active, table.regs.combat, rng)
            on.send(CombatCommandMsg(command=command or EndTurnCommand(actor_id=active)))
            await table.settle()
        assert not table.in_combat and table.turn_key is None
        assert any(isinstance(e.event, EncounterEnded) for e in table.log)
        msgs = seats[0].drain()
        assert of_type(msgs, CombatState)[-1].combat is None
        assert of_type(msgs, NarrationDone), "round segments were narrated"
        assert table.state.memory.narration
        assert_replays(table)


async def test_end_turn_hands_over_and_monsters_act_in_between(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), turn_seconds=None) as (table, clock):
        seats = list(await _fight(table))
        on, _ = _seat_of(seats, table)
        first = _active(table)
        assert clock.pending() == 0
        on.send(CombatCommandMsg(command=EndTurnCommand(actor_id=first)))
        await table.settle()
        assert not table.in_combat or _active(table) != first or table.state.encounter is None


async def test_combat_view_carries_monster_index_and_zone_terrain(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        await _fight(table)
        view = public_combat(table.state)
        assert view is not None
        goblins = [tk for tk in view.tokens if tk.creature_id.startswith("goblin")]
        assert goblins and all(tk.monster_index == "goblin" for tk in goblins)
        assert all(tk.monster_index is None for tk in view.tokens if tk.side.value == "party")
        assert all(zone.terrain for zone in view.zones)
