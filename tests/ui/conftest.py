"""UI test fixtures: the real app on a free port (FakeLLM, temp saves, fake LAN url)."""

import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
import uvicorn

from aidm.server.app import create_app
from aidm.server.settings import server_settings_from_env

ROOT = Path(__file__).resolve().parent.parent.parent
SHOTS = ROOT / "artifacts" / "ui"


@dataclass(frozen=True)
class LiveServer:
    base: str


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def live_server(tmp_path: Path) -> Iterator[LiveServer]:
    port = free_port()
    settings = server_settings_from_env(
        {"AIDM_FAKE_LLM": "1"}, port=port, saves_dir=tmp_path / "saves"
    )
    settings = replace(
        settings,
        llm=replace(settings.llm, log_path=None),
        lan_url=f"http://192.168.1.20:{port}/",
    )
    config = uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started, "server did not start"
    yield LiveServer(base=f"http://127.0.0.1:{port}")
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="session")
def shots_dir() -> Path:
    SHOTS.mkdir(parents=True, exist_ok=True)
    return SHOTS
