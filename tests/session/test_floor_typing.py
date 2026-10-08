"""M11.2: device roles, the public typing line and floor, and the phone's combat target list."""

from pathlib import Path

from aidm.models.encounter import Side
from aidm.models.protocol_client import DeviceRole, Hello, SubmitAction, Typing
from aidm.models.protocol_server import (
    CombatState,
    ErrorCode,
    ErrorMsg,
    FloorState,
    Snapshot,
    TurnPrompt,
)
from aidm.models.protocol_views import PublicCombat
from aidm.session.floor import TYPING_SECONDS
from aidm.session.table import Table
from tests.session.defeat_fixtures import hurt, party_of
from tests.session.table_fixtures import (
    Seat,
    disabled_llm,
    join,
    of_type,
    running,
    screen_seat,
    start_fight,
)


def _typing(seat: Seat) -> list[list[str]]:
    return [[t.name for t in m.floor.typing] for m in of_type(seat.drain(), FloorState)]


async def test_hello_role_screen_watches_and_controller_is_seated(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        screen = await screen_seat(table)
        assert table.players == {} and screen.conn.id in table.spectators
        snap = of_type(screen.drain(), Snapshot)[-1]
        assert snap.state.screens == 1
        conn = table.connect()
        table.submit(conn.id, Hello(name="Sam", role=DeviceRole.CONTROLLER))
        await table.settle()
        assert [p.name for p in table.players.values()] == ["Sam"]
        screen.send(Typing(on=True))
        await table.settle()
        refused = of_type(screen.drain(), ErrorMsg)
        assert refused and refused[-1].code is ErrorCode.REFUSED, "a screen cannot type"


async def test_typing_is_broadcast_refreshed_quietly_and_expires(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, clock):
        sam = await join(table, "Sam", "fighter")
        await join(table, "Mira", "rogue")
        screen = await screen_seat(table)
        screen.drain()
        sam.send(Typing(on=True))
        await table.settle()
        assert _typing(screen) == [["Sam"]]
        clock.advance(TYPING_SECONDS - 1)
        sam.send(Typing(on=True))  # still composing: refresh, no broadcast
        await table.settle()
        assert _typing(screen) == []
        clock.advance(TYPING_SECONDS - 1)
        await table.settle()
        assert table.typing.ids() == [sam.player_id], "the refresh moved the expiry"
        clock.advance(1.5)
        await table.settle()
        assert _typing(screen) == [[]], "expired after the quiet period"
        assert table.snapshot().state.floor.typing == ()


async def test_submitting_or_leaving_stops_typing(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        sam = await join(table, "Sam", "fighter")
        mira = await join(table, "Mira", "rogue")
        screen = await screen_seat(table)
        sam.send(Typing(on=True))
        mira.send(Typing(on=True))
        await table.settle()
        screen.drain()
        sam.send(SubmitAction(text="look around"))
        await table.settle()
        assert table.typing.ids() == [mira.player_id]
        assert ["Mira"] in _typing(screen)
        table.disconnect(mira.conn.id)
        await table.settle()
        assert table.typing.ids() == []


async def test_typing_is_rate_limited_and_refused_when_defeated(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), party_of("fighter")) as (table, _):
        sam = await join(table, "Sam", "fighter")
        for n in range(30):
            sam.send(Typing(on=n % 2 == 0))
        await table.settle()
        assert len(_typing(sam)) == 12, "at most 12 typing messages per window count"
        await hurt(table, "fighter", 999)
        assert table.typing.ids() == []
        sam.drain()
        sam.send(Typing(on=True))
        await table.settle()
        errors = of_type(sam.drain(), ErrorMsg)
        assert errors and errors[-1].refusal == "defeated"


def _chips(combat: PublicCombat) -> list[tuple[str, str, Side, str, float, tuple[str, ...]]]:
    """What a phone needs for target chips: id, name, side, zone name, hp fraction, conditions."""
    zones = {z.id: z.name for z in combat.zones}
    return [
        (t.creature_id, t.name, t.side, zones[t.zone_id], t.hp / t.max_hp, t.conditions)
        for t in combat.tokens
        if not t.dead and not t.withdrawn
    ]


async def _fight(table: Table) -> tuple[Seat, Seat, Seat]:
    sam = await join(table, "Sam", "fighter")
    mira = await join(table, "Mira", "rogue")
    screen = await screen_seat(table)
    await start_fight(table, "goblin", "goblin")
    return sam, mira, screen


async def test_combat_state_is_enough_for_phone_target_chips(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        sam, _mira, screen = await _fight(table)
        msgs = sam.drain()
        combat = of_type(msgs, CombatState)[-1].combat
        prompt = of_type(msgs, TurnPrompt)[-1]
        assert combat is not None and prompt.creature_id == combat.active_id
        enc = table.state.encounter
        assert enc is not None
        chips = _chips(combat)
        assert {c[0] for c in chips} == set(enc.combatants)
        assert {c[2] for c in chips} == {Side.PARTY, Side.HOSTILE}
        assert all(c[1] and c[3] and 0 < c[4] <= 1 for c in chips)
        holder = table.snapshot().state.floor.holder
        owner = table.owner_of(combat.active_id)
        assert (holder.player_id if holder else None) == (owner.id if owner else None)
        assert of_type(screen.drain(), CombatState), "the screen draws the same board"
