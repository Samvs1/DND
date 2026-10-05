"""UI test fixtures: the real app on a free port (FakeLLM, temp saves, fake LAN url)."""

import socket
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import Browser, sync_playwright

from aidm.dm.fake_llm import FakeLLM, FakeStep, default_fake_step, fake_tool_call
from aidm.dm.llm_backend import CompletionRequest
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmMode
from aidm.server.app import create_app
from aidm.server.settings import ServerSettings, server_settings_from_env

ROOT = Path(__file__).resolve().parent.parent.parent
SHOTS = ROOT / "artifacts" / "ui"


@dataclass(frozen=True)
class LiveServer:
    base: str


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _serve(
    tmp_path: Path, llm_for: Callable[[ServerSettings], LlmClient] | None = None
) -> Iterator[LiveServer]:
    port = free_port()
    settings = server_settings_from_env(
        {"AIDM_FAKE_LLM": "1"}, port=port, saves_dir=tmp_path / "saves"
    )
    settings = replace(
        settings,
        llm=replace(settings.llm, log_path=None),
        lan_url=f"http://192.168.1.20:{port}/",
    )
    llm = llm_for(settings) if llm_for else None
    config = uvicorn.Config(
        create_app(settings, llm=llm), host="127.0.0.1", port=port, log_level="warning"
    )
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


@pytest.fixture
def live_server(tmp_path: Path) -> Iterator[LiveServer]:
    yield from _serve(tmp_path)


def _search_responder(request: CompletionRequest) -> FakeStep:
    """FakeLLM that turns a "search" action into ONE investigation check for the first hero."""
    names = [t["function"]["name"] for t in request.tools or []]
    last = next((m for m in reversed(request.messages) if m.get("role") == "user"), {})
    already = any(m.get("role") == "tool" for m in request.messages)
    if (
        "request_check" in names
        and "search" in str(last.get("content", "")).lower()
        and not already
    ):
        args = {
            "actor": "Brienne",
            "ability_or_skill": "investigation",
            "dc_tier": "easy",
            "reason": "searching the room",
        }
        return fake_tool_call("request_check", args)
    return default_fake_step(request)


@pytest.fixture
def scripted_server(tmp_path: Path) -> Iterator[LiveServer]:
    """Like `live_server`, but a search action makes the DM request a skill check (dice)."""

    def make(settings: ServerSettings) -> LlmClient:
        return LlmClient(FakeLLM(responder=_search_responder), settings.llm, LlmMode.FAKE, None)

    yield from _serve(tmp_path, make)


@pytest.fixture(scope="session")
def shots_dir() -> Path:
    SHOTS.mkdir(parents=True, exist_ok=True)
    return SHOTS


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as pw:
        chromium = pw.chromium.launch()
        yield chromium
        chromium.close()
