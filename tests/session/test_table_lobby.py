"""Table actor: seats, reconnect, character creation, campaign start, hostile confirm (M6.2)."""

from pathlib import Path

from aidm.dm.fake_llm import fake_calls
from aidm.models.creation import AbilityMethod, CreationErrorCode
from aidm.models.protocol_client import (
    CancelHostile,
    ConfirmHostile,
    CreateCharacter,
    Hello,
    HostKick,
    HostStart,
    RollAbilities,
    SubmitAction,
)
from aidm.models.protocol_server import (
    AbilityRolls,
    CombatState,
    CreationResult,
    ErrorCode,
    ErrorMsg,
    EventMsg,
    LobbyRoster,
    NarrationDone,
    Notice,
    NoticeKind,
    PendingConfirmationMsg,
    Snapshot,
    TurnPrompt,
    Welcome,
)
from aidm.models.protocol_views import TablePhase
from aidm.models.state import GameState
from tests.session.table_fixtures import (
    assert_replays,
    disabled_llm,
    drain_queue,
    fake_llm,
    join,
    menu_llm,
    of_type,
    pick,
    running,
)
from tests.unit.rules.creation_fixtures import default_choices


async def test_first_player_hosts_and_reconnect_keeps_the_seat(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), GameState(campaign_id="t", seed=1)) as (table, _):
        ann = await join(table, "Ann")
        bob = await join(table, "Bob")
        assert table.players[ann.player_id].is_host
        assert not table.players[bob.player_id].is_host
        table.disconnect(bob.conn.id)
        await table.settle()
        roster = of_type(ann.drain(), LobbyRoster)[-1]
        assert [p.connected for p in roster.players] == [True, False]
        again = table.connect()
        table.submit(again.id, Hello(name="Bob", token=bob.token))
        await table.settle()
        msgs = drain_queue(again)
        welcome = of_type(msgs, Welcome)[0]
        assert welcome.player_id == bob.player_id and not welcome.is_host
        snap = of_type(msgs, Snapshot)[0]
        assert snap.seq == table.state.event_count
        assert snap.state.phase is TablePhase.LOBBY
        assert len(table.players) == 2


async def test_create_character_roll_check_and_errors(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), GameState(campaign_id="t", seed=1)) as (table, _):
        ann = await join(table, "Ann")
        choices = default_choices("fighter", "human", None).model_copy(update={"name": "Ann"})
        bad = choices.model_copy(update={"race": "unicorn"})
        ann.send(CreateCharacter(choices=bad))
        ann.send(RollAbilities())
        await table.settle()
        msgs = ann.drain()
        assert not of_type(msgs, CreationResult)[0].ok
        rolls = of_type(msgs, AbilityRolls)[0].rolls
        forged = choices.model_copy(
            update={"ability_method": AbilityMethod.ROLL_4D6, "rolls": list(rolls[::-1])}
        )
        ann.send(CreateCharacter(choices=forged))
        await table.settle()
        result = of_type(ann.drain(), CreationResult)[0]
        assert not result.ok
        assert CreationErrorCode.ROLLS_INVALID in {e.code for e in result.errors}
        ann.send(CreateCharacter(choices=choices))
        await table.settle()
        result = of_type(ann.drain(), CreationResult)[0]
        assert result.ok and result.sheet is not None and result.sheet.name == "Ann"
        assert table.players[ann.player_id].creature_id in table.state.creatures
        assert_replays(table)


async def test_host_start_installs_campaign_and_narrates(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), GameState(campaign_id="t", seed=3)) as (table, _):
        ann = await join(table, "Ann")
        bob = await join(table, "Bob")
        ann.send(HostStart(theme="salt and storms"))
        await table.settle()
        assert of_type(ann.drain(), ErrorMsg)[0].code is ErrorCode.NO_CHARACTER
        choices = default_choices("fighter", "human", None).model_copy(update={"name": "Ann"})
        ann.send(CreateCharacter(choices=choices))
        bob.send(HostStart())
        ann.send(HostStart(theme="salt and storms"))
        await table.settle()
        assert of_type(bob.drain(), ErrorMsg)[0].code is ErrorCode.NOT_HOST
        msgs = ann.drain()
        progress = [n for n in of_type(msgs, Notice) if n.kind is NoticeKind.PROGRESS]
        assert progress, "generation shows a progress notice"
        assert table.phase is TablePhase.PLAY and table.state.campaign is not None
        assert of_type(msgs, NarrationDone), "opening narration"
        snap = of_type(msgs, Snapshot)[-1]
        assert snap.state.scene is not None and snap.state.campaign_title
        ann.send(HostKick(player_id=bob.player_id))
        await table.settle()
        assert bob.player_id not in table.players
        assert of_type(ann.drain(), Notice)[-1].text.endswith("removed from the table.")
        assert_replays(table)


async def test_hostile_act_waits_for_confirmation(tmp_path: Path) -> None:
    attack = fake_calls([("start_encounter", {"against_npcs": ["npc-mira"]})])
    llm, _ = fake_llm(tmp_path, [attack])
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        ann.send(SubmitAction(text="I attack Mira"))
        await table.settle()
        prompts = of_type(ann.drain(), PendingConfirmationMsg)
        assert prompts and prompts[0].player_id == ann.player_id
        assert not of_type(bob.drain(), PendingConfirmationMsg)
        assert not table.combat_active() and table.pending is not None
        bob.send(ConfirmHostile())
        await table.settle()
        assert of_type(bob.drain(), ErrorMsg)[0].code is ErrorCode.REFUSED
        ann.send(ConfirmHostile())
        await table.settle()
        assert table.state.encounter is not None
        msgs = ann.drain() + bob.drain()
        assert of_type(msgs, CombatState) or of_type(msgs, TurnPrompt)
        assert table.state.world.npcs["npc-mira"].hostile
        assert_replays(table)


async def test_cancelled_hostile_act_changes_nothing(tmp_path: Path) -> None:
    attack = fake_calls([("start_encounter", {"against_npcs": ["npc-mira"]})])
    llm, _ = fake_llm(tmp_path, [attack])
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I attack Mira"))
        await table.settle()
        ann.drain()
        ann.send(CancelHostile())
        await table.settle()
        assert table.pending is None and table.state.encounter is None
        assert of_type(ann.drain(), NarrationDone)
        assert not table.state.world.npcs["npc-mira"].hostile


async def test_hello_with_last_seq_resends_only_missed_events(tmp_path: Path) -> None:
    rest = pick(("rest:short", [], None))
    llm = menu_llm(tmp_path, rest, pick(other=""), rest)[0]
    async with running(llm, interpreter="menu") as (table, _):
        host = await join(table, "Ann", "fighter")
        for text in ("we take a short rest", "I warm my hands", "we take a short rest"):
            host.send(SubmitAction(text=text))
            await table.settle()
        public = table.public.events
        assert [m.kind for m in public] == ["short_rest_taken", "short_rest_taken"]
        cut = public[0].seq + 1
        conn = table.connect()
        table.submit(conn.id, Hello(name="Ann", token=host.token, last_seq=cut))
        await table.settle()
        events = of_type(drain_queue(conn), EventMsg)
        assert [e.seq for e in events] == [public[1].seq]


async def test_screen_is_counted_watches_and_cannot_act(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), GameState(campaign_id="t", seed=1)) as (table, _):
        ann = await join(table, "Ann")
        assert table.snapshot().state.screens == 0
        screen = table.connect()
        table.submit(screen.id, Hello(name="screen", spectator=True))
        await table.settle()
        got = drain_queue(screen)
        assert [m.type for m in got][:2] == ["snapshot", "story_history"]
        assert not of_type(got, Welcome) and not table.players[ann.player_id].conns & {screen.id}
        assert of_type(got, Snapshot)[0].state.screens == 1
        assert of_type(ann.drain(), Snapshot)[-1].state.screens == 1  # players learn of the screen
        assert len(table.players) == 1  # a spectator takes no seat
        table.submit(screen.id, SubmitAction(text="I attack the host"))
        table.submit(screen.id, RollAbilities())
        table.submit(screen.id, HostKick(player_id=ann.player_id))
        await table.settle()
        refused = of_type(drain_queue(screen), ErrorMsg)
        assert [e.code for e in refused] == [ErrorCode.REFUSED] * 3
        assert table.queue == type(table.queue)() and ann.player_id in table.players
        table.disconnect(screen.id)
        await table.settle()
        assert table.snapshot().state.screens == 0
        assert of_type(ann.drain(), Snapshot)[-1].state.screens == 0
