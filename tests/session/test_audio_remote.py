"""M11.2: the audio remote. Any seated player sets the shared screen's narration and music
volume and mutes; table state (table.json), not an event; in every snapshot; last write wins."""

import json
from pathlib import Path

from starlette.testclient import TestClient

from aidm.models.protocol_client import AudioSettingsMsg
from aidm.models.protocol_server import AudioSettingsState, ErrorCode, ErrorMsg, Snapshot
from aidm.models.protocol_views import AudioSettings, TablePhase
from aidm.session.persistence import TABLE, CampaignStore
from aidm.session.restore import restore
from aidm.session.table import Table
from aidm.session.table_core import TableConfig
from tests.ai.guard_fixtures import inn_state
from tests.session.defeat_fixtures import hurt, party_of
from tests.session.server_fixtures import hello, make_app, read_until
from tests.session.table_fixtures import (
    disabled_llm,
    join,
    join_with_token,
    of_type,
    running,
    screen_seat,
)

QUIET = AudioSettingsMsg(narration_volume=35, music_volume=10, music_muted=True)


def test_audio_defaults_are_narration_80_music_50_unmuted() -> None:
    audio = AudioSettings()
    assert (audio.narration_volume, audio.music_volume) == (80, 50)
    assert not audio.narration_muted and not audio.music_muted


async def test_a_player_sets_the_screen_audio_and_it_survives_a_reload(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "saves")
    llm = disabled_llm(tmp_path)
    async with running(llm, inn_state(), store=store) as (table, _):
        ann = await join(table, "Ann", "fighter")
        screen = await screen_seat(table)
        table.autosave(force=True)
        count = table.state.event_count
        ann.send(QUIET)
        await table.settle()
        got = of_type(screen.drain(), AudioSettingsState)
        assert [m.settings.music_volume for m in got] == [10] and got[0].settings.music_muted
        assert of_type(ann.drain(), AudioSettingsState), "every seat sees the new levels"
        assert table.state.event_count == count, "audio is table state, not an event"
        late = await screen_seat(table)
        assert of_type(late.drain(), Snapshot)[-1].state.audio.narration_volume == 35
        cid, token = table.state.campaign_id, ann.token
        saved = json.loads((store.root / cid / TABLE).read_text(encoding="utf-8"))
        assert saved["audio"]["music_volume"] == 10, "written at once, before any autosave"
    fresh = Table(inn_state(), llm, TableConfig(store=store))
    restore(fresh, store.load(cid))
    async with fresh:
        await join_with_token(fresh, "Ann", token)
        again = await screen_seat(fresh)
        audio = of_type(again.drain(), Snapshot)[-1].state.audio
        assert audio == AudioSettings(narration_volume=35, music_volume=10, music_muted=True)


async def test_audio_is_rate_limited_and_allowed_while_defeated(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path), party_of("fighter")) as (table, _):
        sam = await join(table, "Sam", "fighter")
        await hurt(table, "fighter", 999)
        assert table.phase is TablePhase.DEFEATED
        sam.drain()
        for volume in range(25):
            sam.send(AudioSettingsMsg(narration_volume=volume, music_volume=50))
        await table.settle()
        msgs = sam.drain()
        assert len(of_type(msgs, AudioSettingsState)) == 20
        refusals = {e.refusal for e in of_type(msgs, ErrorMsg)}
        assert refusals == {"rate_limited"}, "the defeat lock lets the audio remote through"
        assert table.audio.narration_volume == 19


def test_out_of_range_and_screen_audio_are_refused_on_the_socket(tmp_path: Path) -> None:
    app = make_app(tmp_path, state=inn_state())
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        hello(ws, "Ann", role="controller")
        read_until(ws, "story_history")
        bad = {"narration_volume": 101, "music_volume": 50}
        ws.send_json({"type": "audio_settings", **bad})
        assert read_until(ws, "error")[-1]["code"] == ErrorCode.INVALID.value
        with client.websocket_connect("/ws") as screen:
            hello(screen, "screen", role="screen")
            snap = read_until(screen, "snapshot")[-1]
            assert snap["state"]["audio"] == AudioSettings().model_dump()
            screen.send_json({"type": "audio_settings", "narration_volume": 5, "music_volume": 5})
            assert read_until(screen, "error")[-1]["code"] == ErrorCode.REFUSED.value
