"""Server: websocket join, actions, reconnect catch-up, bad input, /healthz, CLI (M6.4)."""

import json
import subprocess
import sys
from pathlib import Path

from starlette.testclient import TestClient

from aidm.models.protocol import server_adapter
from aidm.server.app import create_app
from aidm.server.ws import MAX_FRAME_CHARS
from tests.ai.guard_fixtures import inn_state
from tests.session.server_fixtures import (
    hello,
    make_app,
    read_until,
    registry_of,
    settings_of,
)

ROOT = Path(__file__).resolve().parent.parent.parent


def test_join_gets_welcome_and_snapshot(tmp_path: Path) -> None:
    with TestClient(make_app(tmp_path)) as client, client.websocket_connect("/ws") as ws:
        hello(ws, "Ann")
        msgs = read_until(ws, "snapshot")
        assert [m["type"] for m in msgs] == ["welcome", "snapshot"]
        assert ws.receive_json()["type"] == "story_history"
        assert msgs[0]["is_host"] is True and msgs[0]["token"]
        assert msgs[1]["seq"] == 0
        for msg in msgs:
            server_adapter.validate_python(msg)


def test_submit_action_streams_events_then_narration(tmp_path: Path) -> None:
    app = make_app(tmp_path, state=inn_state())
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        hello(ws, "Ann")
        welcome = read_until(ws, "snapshot")[0]
        registry_of(app).table.players[welcome["player_id"]].creature_id = "fighter"
        ws.send_json({"type": "submit_action", "text": "I warm my hands by the hearth"})
        msgs = read_until(ws, "narration_done")
        kinds = [m["type"] for m in msgs]
        assert "narration_chunk" in kinds and kinds[-1] == "narration_done"
        tail = read_until(ws, "snapshot")
        # The recorded narration is bookkeeping, not a public event: it is never sent.
        assert not [m for m in msgs + tail if m["type"] == "event"]
        assert tail[-1]["seq"] == registry_of(app).table.state.event_count


REST_ACTIONS = ("we take a short rest", "I warm my hands by the hearth", "we take a short rest")


def test_reconnect_with_last_seq_gets_only_missed_events(tmp_path: Path) -> None:
    app = make_app(tmp_path, state=inn_state())
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            hello(ws, "Ann")
            welcome = read_until(ws, "snapshot")[0]
            registry_of(app).table.players[welcome["player_id"]].creature_id = "fighter"
            for text in REST_ACTIONS:
                ws.send_json({"type": "submit_action", "text": text})
                read_until(ws, "narration_done")
        table = registry_of(app).table
        public = table.public.events
        assert len(public) == 2
        cut = public[0].seq + 1
        with client.websocket_connect("/ws") as ws2:
            hello(ws2, "Ann", token=welcome["token"], last_seq=cut)
            msgs = read_until(ws2, "lobby_roster")
        assert msgs[0]["type"] == "welcome" and msgs[0]["player_id"] == welcome["player_id"]
        assert msgs[1]["type"] == "snapshot" and msgs[1]["seq"] == table.log[-1].seq + 1
        assert msgs[2]["type"] == "story_history"
        got = [m["seq"] for m in msgs if m["type"] == "event"]
        assert got == [public[1].seq]


def test_invalid_input_gets_an_error_and_the_socket_stays_open(tmp_path: Path) -> None:
    with TestClient(make_app(tmp_path)) as client, client.websocket_connect("/ws") as ws:
        for bad in ("not json at all", json.dumps({"type": "no_such"}), "[1, 2]"):
            ws.send_text(bad)
            err = ws.receive_json()
            assert err["type"] == "error" and err["code"] == "invalid"
            assert "Traceback" not in err["text"] and "pydantic" not in err["text"]
        ws.send_text("x" * (MAX_FRAME_CHARS + 1))
        assert ws.receive_json()["type"] == "error"
        ws.send_bytes(b"\x00\x01")
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"type": "submit_action", "text": "hi"})
        assert ws.receive_json()["code"] == "not_joined"
        hello(ws, "Ann")
        assert [m["type"] for m in read_until(ws, "snapshot")] == ["welcome", "snapshot"]


def test_healthz_has_booleans_and_no_key_material(tmp_path: Path) -> None:
    secrets = {
        "DEEPSEEK_API_KEY": "sk-test-deepseek-9f3a1c",
        "FISH_API_KEY": "fish-test-key-77aa21",
        "FISH_VOICE_ID": "voice-test-id-55bb90",
    }
    app = make_app(tmp_path, {**secrets, "TTS_ENABLED": "1"})
    with TestClient(app) as client:
        reply = client.get("/healthz")
        body = reply.json()
        assert set(body) == {"ok", "deepseek", "fish", "tts_enabled", "version"}
        assert body["ok"] is True and body["deepseek"] is True and body["fish"] is True
        assert body["tts_enabled"] is True and isinstance(body["version"], str)
        for value in secrets.values():
            assert value not in reply.text
            assert value not in repr(settings_of(app))


def test_healthz_without_keys_reports_false(tmp_path: Path) -> None:
    with TestClient(make_app(tmp_path, {"AIDM_FAKE_LLM": "0"})) as client:
        body = client.get("/healthz").json()
        assert body["deepseek"] is False and body["fish"] is False
        assert body["tts_enabled"] is False


def test_pages_static_and_lan_qr(tmp_path: Path) -> None:
    with TestClient(make_app(tmp_path)) as client:
        for route in ("/", "/play", "/screen"):
            assert client.get(route).status_code == 200
        assert client.get("/web/protocol.json").status_code == 200
        assert client.get("/api/lan-qr.svg").status_code == 404
        assert client.get("/api/saves").json() == []
    app = make_app(tmp_path, lan_url="http://192.168.1.20:8000/")
    with TestClient(app) as client:
        svg = client.get("/api/lan-qr.svg")
        assert svg.status_code == 200 and b"<svg" in svg.content
        assert svg.headers["content-type"].startswith("image/svg+xml")
        assert client.get("/api/lan").json()["url"] == "http://192.168.1.20:8000/"


def test_python_m_aidm_help_works() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "aidm", "--help"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
        check=False,
    )
    assert done.returncode == 0
    assert "--lan" in done.stdout and "--port" in done.stdout and "--host" in done.stdout


def test_a_played_game_is_saved_and_reopened_by_campaign_id(tmp_path: Path) -> None:
    state = inn_state()
    app = make_app(tmp_path, state=state)
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        hello(ws, "Ann")
        welcome = read_until(ws, "snapshot")[0]
        registry_of(app).table.players[welcome["player_id"]].creature_id = "fighter"
        ws.send_json({"type": "submit_action", "text": "I search behind the hearth"})
        read_until(ws, "narration_done")
        read_until(ws, "snapshot")
        saves = client.get("/api/saves").json()
    assert [s["campaign_id"] for s in saves] == [state.campaign_id]
    again = create_app(settings_of(app), campaign_id=state.campaign_id)
    with TestClient(again) as client, client.websocket_connect("/ws") as ws:
        hello(ws, "Ann", token=welcome["token"])
        msgs = read_until(ws, "snapshot")
        assert msgs[0]["player_id"] == welcome["player_id"] and msgs[0]["is_host"] is True
        assert msgs[1]["seq"] == saves[0]["seq"]


def test_spectator_socket_gets_the_public_feed_and_cannot_act(tmp_path: Path) -> None:
    app = make_app(tmp_path, state=inn_state())
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        hello(ws, "screen", spectator=True)
        msgs = read_until(ws, "story_history")
        assert [m["type"] for m in msgs] == ["snapshot", "story_history"]
        assert msgs[0]["state"]["screens"] == 1
        assert registry_of(app).table.players == {}  # no seat
        ws.send_json({"type": "submit_action", "text": "I attack"})
        refusal = read_until(ws, "error")[-1]
        assert refusal["code"] == "refused"
        ws.send_json({"type": "ping"})
        assert read_until(ws, "pong")[-1]["type"] == "pong"
