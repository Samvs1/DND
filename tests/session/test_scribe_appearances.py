"""The Scribe's appearances over the table actor (M13.2): welcome first / back, fight and campaign
victory, the victory state after a reconnect. FakeLLM or the disabled client only."""

from pathlib import Path

from aidm.models.campaign_state import OfferChoice
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import CreatureDied
from aidm.models.protocol import AnyServerMsg
from aidm.models.protocol_client import (
    ChooseFinale,
    CreateCharacter,
    Hello,
    HostLoad,
    HostStart,
    SubmitAction,
)
from aidm.models.protocol_server import (
    EpilogueMsg,
    NarrationChunkMsg,
    NarrationDone,
    ScribeLineMsg,
    Snapshot,
)
from aidm.models.state import GameState
from aidm.session import combat_flow
from aidm.session.persistence import CampaignStore
from aidm.session.restore import restore
from aidm.session.scribe_voice import welcome_back_later
from aidm.session.table import Table
from tests.ai.epilogue_fixtures import kill_foes
from tests.ai.fake_scripts import fake_client
from tests.ai.guard_fixtures import inn_state
from tests.asset_helpers import expected_audio_url
from tests.session.progression_fixtures import answer, campaign_state, move, plan
from tests.session.table_fixtures import (
    Seat,
    assert_replays,
    disabled_llm,
    drain_queue,
    join,
    join_with_token,
    menu_llm,
    of_type,
    pick,
    running,
    screen_seat,
    start_fight,
)
from tests.unit.rules.creation_fixtures import default_choices

SEARCH = pick(("search:investigation", [], None))  # "I search behind the hearth" (M36.10a)


def _groups(msgs: list[AnyServerMsg]) -> list[str]:
    return [m.group for m in of_type(msgs, ScribeLineMsg)]


def _index(msgs: list[AnyServerMsg], kind: type) -> int:
    return next(i for i, m in enumerate(msgs) if isinstance(m, kind))


async def _hero(table: Table, name: str, cls: str) -> Seat:
    seat = await join(table, name)
    choices = default_choices(cls, "human", None).model_copy(update={"name": name})
    seat.send(CreateCharacter(choices=choices))
    await table.settle()
    return seat


async def _win(table: Table) -> None:
    async def job() -> None:
        enc = table.state.encounter
        assert enc is not None
        for cid, combatant in sorted(enc.combatants.items()):
            if combatant.side is Side.HOSTILE:
                table.apply(CreatureDied(creature_id=cid))
        await combat_flow.finish_fight(table, EncounterStatus.VICTORY)

    table.schedule(job)
    await table.settle()


def _final_fight() -> GameState:
    """The sample campaign with every region resolved but the last boss fight still running."""
    _, state, log = campaign_state()
    for act in range(3):
        region = plan().acts[act].region
        if act:
            move(state, region.arrival.id, log)
        for spoke in region.spokes:
            if state.world.current_node != region.arrival.id:
                move(state, region.arrival.id, log)
            move(state, spoke.id, log)
            answer(state, OfferChoice.FIGHT, log)
            kill_foes(state, log)
        move(state, region.gateway.id, log)
        answer(state, OfferChoice.FIGHT, log)
        if act < 2:
            kill_foes(state, log)
    return state


async def test_new_campaign_welcome_comes_before_the_opening_narration(tmp_path: Path) -> None:
    llm, _ = fake_client(tmp_path)
    async with running(llm, GameState(campaign_id="t", seed=3)) as (table, _):
        ann = await _hero(table, "Ann", "fighter")
        screen = await screen_seat(table)
        ann.drain()
        screen.drain()
        count = table.state.event_count
        table.submit(ann.conn.id, Hello(name="Ann", token=ann.token))
        await table.settle()
        assert _groups(ann.drain()) == [] and table.state.event_count == count
        ann.send(HostStart())
        await table.settle()
        for msgs in (ann.drain(), screen.drain()):
            lines = of_type(msgs, ScribeLineMsg)
            assert [(m.group, m.line_id, m.to_player_id) for m in lines] == [
                ("welcome_first", "welcome.first", None)
            ]
            assert (
                lines[0].text.startswith("Ah. So ye have come at last.")
                and "[" not in lines[0].text
            )
            assert lines[0].audio_url == expected_audio_url("welcome.first")
            assert _index(msgs, ScribeLineMsg) < _index(msgs, NarrationChunkMsg)
        assert_replays(table)


async def test_welcome_starts_while_the_world_is_being_written(tmp_path: Path) -> None:
    """M18.1 owner request: his welcome covers the campaign generation wait. The line arrives after
    the GENERATING snapshot and before the first snapshot of the installed world (phase play)."""
    llm, _ = fake_client(tmp_path)
    async with running(llm, GameState(campaign_id="t", seed=3)) as (table, _):
        ann = await _hero(table, "Ann", "fighter")
        ann.drain()
        ann.send(HostStart())
        await table.settle()
        msgs = ann.drain()
    phases = [(i, m.state.phase.value) for i, m in enumerate(msgs) if isinstance(m, Snapshot)]
    generating = next(i for i, phase in phases if phase == "generating")
    playing = next(i for i, phase in phases if phase == "play")
    assert generating < _index(msgs, ScribeLineMsg) < playing


async def test_host_load_welcomes_back_but_not_a_lobby_save(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    llm = menu_llm(tmp_path, SEARCH)[0]
    async with running(llm, inn_state(), store=store) as (first, _):
        ann = await join(first, "Ann", "fighter")
        ann.send(SubmitAction(text="I search behind the hearth"))
        await first.settle()
        saved_id = first.state.campaign_id
    lobby = GameState(campaign_id="lobby-save", seed=4)
    async with running(disabled_llm(tmp_path), lobby, store=store) as (table, _):
        cara = await join(table, "Cara")
        table.autosave(force=True)
        cara.drain()
        cara.send(HostLoad(campaign_id=saved_id))
        await table.settle()
        msgs = cara.drain()
        assert _groups(msgs) == ["welcome_return"]
        assert _index(msgs, Snapshot) < _index(msgs, ScribeLineMsg)
        cara.send(HostLoad(campaign_id="lobby-save"))
        await table.settle()
        assert _groups(cara.drain()) == []


async def test_boot_load_welcomes_back_once_on_the_first_connection(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    llm = menu_llm(tmp_path, pick(("look", [], None)))[0]
    async with running(llm, inn_state(), store=store) as (first, _):
        ann = await join(first, "Ann", "fighter")
        ann.send(SubmitAction(text="I look around"))
        await first.settle()
        saved_id, token = first.state.campaign_id, ann.token
    async with running(disabled_llm(tmp_path), GameState(campaign_id="x", seed=1)) as (table, _):
        restore(table, store.load(saved_id))
        welcome_back_later(table)
        screen = await screen_seat(table)
        assert _groups(screen.drain()) == ["welcome_return"]
        back = await join_with_token(table, "Ann", token)
        assert _groups(back.drain() + screen.drain()) == []


async def test_won_fight_gets_no_scribe_line(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), inn_state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        await start_fight(table, "wolf")
        ann.drain()
        await _win(table)
        msgs = ann.drain()
        # Owner feedback (M13.4): he stays silent after an ordinary won fight.
        assert of_type(msgs, ScribeLineMsg) == []
        assert of_type(msgs, NarrationDone)
        assert_replays(table)


async def test_campaign_victory_replaces_the_fight_line_and_survives_reconnect(
    tmp_path: Path,
) -> None:
    async with running(disabled_llm(tmp_path), _final_fight()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        snap = table.snapshot().state
        assert not snap.complete and snap.epilogue is None
        await _win(table)
        assert _groups(ann.drain()) == []  # M23.9: the finale card first, the story is not over
        assert table.snapshot().state.finale is not None
        ann.send(ChooseFinale(option_id="silence-the-song", confirm=True))
        await table.settle()
        msgs = ann.drain()
        assert _groups(msgs) == ["victory_campaign"]
        assert _index(msgs, ScribeLineMsg) < _index(msgs, EpilogueMsg)
        assert table.state.campaign is not None and table.state.campaign.complete
        late = table.connect()
        table.submit(late.id, Hello(name="Ann", token=ann.token, last_seq=0))
        await table.settle()
        again = drain_queue(late)
        assert _groups(again) == []
        state = of_type(again, Snapshot)[-1].state
        assert state.complete and state.epilogue and state.defeat is None
        assert state.phase.value == "ended"
        assert_replays(table)
