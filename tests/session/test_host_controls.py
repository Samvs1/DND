"""Host controls: kick, difficulty, TTS, save, load, new, end, token totals (M6.5)."""

import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm.dm.llm_client import LlmClient
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.events import DamageTaken
from aidm.models.protocol_client import (
    Hello,
    HostDifficulty,
    HostEnd,
    HostForceVote,
    HostKick,
    HostLoad,
    HostNew,
    HostPause,
    HostResume,
    HostSave,
    HostStart,
    HostTtsToggle,
    SubmitAction,
)
from aidm.models.protocol_server import (
    ErrorCode,
    ErrorMsg,
    HostStats,
    Notice,
    NoticeKind,
    QueueState,
    Snapshot,
    Welcome,
)
from aidm.models.protocol_views import TablePhase
from aidm.rules.attacks import deal_damage
from aidm.rules.difficulty import scale_damage
from aidm.session.persistence import CampaignStore
from tests.ai.guard_fixtures import inn_state
from tests.session.table_fixtures import (
    assert_replays,
    disabled_llm,
    drain_queue,
    join,
    join_with_token,
    menu_llm,
    of_type,
    pick,
    running,
    start_fight,
)

SEARCH = pick(("search:investigation", [], None))  # "I search behind the hearth" (M36.10a)


def _searching(tmp_path: Path) -> LlmClient:
    return menu_llm(tmp_path, SEARCH)[0]


HOST_MSGS = [
    HostStart(),
    HostPause(),
    HostResume(),
    HostKick(player_id="p1"),
    HostDifficulty(monster_hp=2.0, monster_damage=2.0),
    HostTtsToggle(enabled=True),
    HostSave(),
    HostLoad(campaign_id="x"),
    HostNew(),
    HostEnd(),
    HostForceVote(),
]


async def test_every_host_control_refuses_a_non_host(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    async with running(disabled_llm(tmp_path), inn_state(), store=store) as (table, _):
        await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        before = (table.state.model_dump(), table.paused, table.tts_enabled, len(table.players))
        for msg in HOST_MSGS:
            bob.send(msg)
        await table.settle()
        errors = of_type(bob.drain(), ErrorMsg)
        assert [e.code for e in errors] == [ErrorCode.NOT_HOST] * len(HOST_MSGS)
        after = (table.state.model_dump(), table.paused, table.tts_enabled, len(table.players))
        assert before == after
        assert not store.list_campaigns()


async def test_kick_removes_the_seat_and_keeps_the_hero(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), inn_state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        ann.send(HostPause())
        bob.send(SubmitAction(text="I hum a tune"))
        ann.send(HostResume())
        await table.settle()
        ann.send(HostPause())
        await table.settle()
        bob.send(SubmitAction(text="I study the rusted lever"))
        await table.settle()
        ann.drain()
        ann.send(HostKick(player_id=bob.player_id))
        await table.settle()
        assert bob.player_id not in table.players and "rogue" in table.state.creatures
        assert all(e.player_id != bob.player_id for e in table.queue)
        msgs = bob.drain()
        assert any(n.kind is NoticeKind.HOST for n in of_type(msgs, Notice))
        bob.send(SubmitAction(text="hello?"))
        again = table.connect()
        table.submit(again.id, Hello(name="Bob", token=bob.token))
        await table.settle()
        assert of_type(bob.drain(), ErrorMsg)[0].code is ErrorCode.NOT_JOINED
        assert of_type(drain_queue(again), ErrorMsg)[0].code is ErrorCode.REFUSED
        assert of_type(ann.drain(), QueueState)
        ann.send(HostKick(player_id=ann.player_id))
        ann.send(HostKick(player_id="p99"))
        await table.settle()
        codes = [e.code for e in of_type(ann.drain(), ErrorMsg)]
        assert codes == [ErrorCode.REFUSED, ErrorCode.UNKNOWN_TARGET]


async def test_difficulty_scales_spawned_hp_and_monster_damage(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), inn_state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(HostDifficulty(monster_hp=2.0, monster_damage=1.5))
        await table.settle()
        assert table.state.difficulty.monster_hp == 2.0
        assert table.state.difficulty.monster_damage == 1.5
        assert of_type(ann.drain(), Notice)
        await start_fight(table, "goblin")
        goblin = table.state.creatures["goblin-1"]
        assert goblin.max_hp == 14 and goblin.hp == 14  # SRD goblin has 7 hp
        packet = DamagePacket(amount=5, damage_type=DamageType.SLASHING)
        assert [p.amount for p in scale_damage(table.state, "goblin-1", [packet])] == [8]
        assert [p.amount for p in scale_damage(table.state, "fighter", [packet])] == [5]
        assert_replays(table)


async def test_difficulty_reaches_the_damage_choke(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), inn_state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        await start_fight(table, "goblin")
        packet = DamagePacket(amount=4, damage_type=DamageType.SLASHING)
        feats = table.regs.combat.chars.features
        state = table.state

        def total() -> int:
            hit = deal_damage(
                random.Random(1), state, "goblin-1", "fighter", [packet], crit=False, feats=feats
            )
            taken = hit[0]
            assert isinstance(taken, DamageTaken)
            return taken.total

        plain = total()
        ann.send(HostDifficulty(monster_hp=1.0, monster_damage=3.0))
        await table.settle()
        assert (plain, total()) == (4, 12)


def test_difficulty_message_is_range_checked() -> None:
    with pytest.raises(ValidationError):
        HostDifficulty(monster_hp=9.0, monster_damage=1.0)
    with pytest.raises(ValidationError):
        HostDifficulty(monster_hp=1.0, monster_damage=0.0)


async def test_tts_toggle_updates_the_table_and_the_snapshot(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    async with running(_searching(tmp_path), inn_state(), store=store, interpreter="menu") as (
        table,
        _,
    ):
        ann = await join(table, "Ann", "fighter")
        assert not table.tts_enabled
        ann.send(SubmitAction(text="I search behind the hearth"))
        await table.settle()
        ann.drain()
        ann.send(HostTtsToggle(enabled=True))
        await table.settle()
        assert table.tts_enabled
        assert of_type(ann.drain(), Snapshot)[-1].state.tts_enabled is True
        meta = store.load(table.state.campaign_id).meta
        assert meta.tts_enabled is True


async def test_save_forces_a_snapshot_and_works_without_a_store(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), inn_state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.drain()
        ann.send(HostSave())
        await table.settle()
        assert "turned off" in of_type(ann.drain(), Notice)[-1].text
    store = CampaignStore(tmp_path / "saves")
    async with running(disabled_llm(tmp_path), inn_state(), store=store) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.drain()
        ann.send(HostSave())
        await table.settle()
        assert of_type(ann.drain(), Notice)[-1].text == "Game saved."
        assert store.exists(table.state.campaign_id)


async def test_load_switches_the_table_to_a_saved_campaign(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    async with running(_searching(tmp_path), inn_state(), store=store, interpreter="menu") as (
        first,
        _,
    ):
        ann = await join(first, "Ann", "fighter")
        ann.send(SubmitAction(text="I search behind the hearth"))
        await first.settle()
        saved_id, saved = first.state.campaign_id, first.state.model_dump()
        ann_token = ann.token
    other = inn_state()
    other.campaign_id = "other-game"
    async with running(disabled_llm(tmp_path), other, store=store) as (table, _):
        cara = await join(table, "Cara")
        cara.drain()
        cara.send(HostLoad(campaign_id="../etc"))
        cara.send(HostLoad(campaign_id="missing"))
        await table.settle()
        assert [e.code for e in of_type(cara.drain(), ErrorMsg)] == [ErrorCode.REFUSED] * 2
        cara.send(HostLoad(campaign_id=saved_id))
        await table.settle()
        assert table.state.campaign_id == saved_id and table.state.model_dump() == saved
        msgs = cara.drain()
        welcome = of_type(msgs, Welcome)[-1]
        assert welcome.is_host is True and welcome.token == cara.token
        assert table.players[welcome.player_id].creature_id is None
        assert of_type(msgs, Snapshot)[-1].state.campaign_id == saved_id
        assert table.phase is TablePhase.PLAY
        assert_replays(table)
        back = await join_with_token(table, "Ann", ann_token)
        assert table.players[back.player_id].creature_id == "fighter"
        assert not table.players[back.player_id].is_host


async def test_new_campaign_resets_the_game_and_keeps_the_seats(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    async with running(_searching(tmp_path), inn_state(), store=store, interpreter="menu") as (
        table,
        _,
    ):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I search behind the hearth"))
        await table.settle()
        old_id = table.state.campaign_id
        ann.drain()
        ann.send(HostNew())
        await table.settle()
        assert table.state.campaign_id != old_id and not table.state.creatures
        assert table.phase is TablePhase.LOBBY and table.log == []
        welcome = of_type(ann.drain(), Welcome)[-1]
        assert welcome.player_id == ann.player_id and welcome.is_host
        assert table.players[ann.player_id].creature_id is None
        assert store.exists(old_id)


async def test_end_closes_the_table_and_refuses_actions(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    async with running(disabled_llm(tmp_path), inn_state(), store=store) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.drain()
        ann.send(HostEnd())
        await table.settle()
        assert table.phase is TablePhase.ENDED
        assert any("ended" in n.text for n in of_type(ann.drain(), Notice))
        ann.send(SubmitAction(text="look around"))
        ann.send(HostEnd())
        await table.settle()
        assert [e.code for e in of_type(ann.drain(), ErrorMsg)] == [ErrorCode.WRONG_PHASE] * 2
        assert store.exists(table.state.campaign_id)


async def test_host_gets_token_totals_and_others_do_not(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), inn_state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        ann.drain()
        bob.drain()
        ann.send(SubmitAction(text="I search behind the hearth"))
        await table.settle()
        assert of_type(ann.drain(), HostStats)
        assert not of_type(bob.drain(), HostStats)
