"""Helpers for server tests: an app on FakeLLM over a temp saves folder, TestClient sockets."""

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from starlette.testclient import WebSocketTestSession

from aidm.dm.fake_llm import FakeLLM
from aidm.models.state import GameState
from aidm.server.app import create_app
from aidm.server.registry import TableRegistry
from aidm.server.settings import ServerSettings, server_settings_from_env

type Msg = dict[str, Any]


def make_app(
    tmp_path: Path,
    env: Mapping[str, str] | None = None,
    state: GameState | None = None,
    **opts: Any,
) -> FastAPI:
    settings = server_settings_from_env(
        {"AIDM_FAKE_LLM": "1", **(env or {})}, saves_dir=tmp_path / "saves"
    )
    settings = replace(settings, llm=replace(settings.llm, log_path=None), **opts)
    return create_app(settings, state=state)


def settings_of(app: FastAPI) -> ServerSettings:
    return app.state.settings


def registry_of(app: FastAPI) -> TableRegistry:
    return app.state.registry


def server_fake(app: FastAPI) -> FakeLLM:
    """The app's FakeLLM backend (AIDM_FAKE_LLM=1), to queue chooser picks on (M36.10)."""
    backend = registry_of(app).llm.backend
    assert isinstance(backend, FakeLLM)
    return backend


def hello(ws: WebSocketTestSession, name: str, **extra: Any) -> None:
    ws.send_json({"type": "hello", "name": name, **extra})


def read_until(ws: WebSocketTestSession, kind: str, limit: int = 400) -> list[Msg]:
    """Receive messages up to and including the first of type `kind`."""
    seen: list[Msg] = []
    for _ in range(limit):
        msg: Msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] == kind:
            return seen
    raise AssertionError(f"no {kind} within {limit} messages: {[m['type'] for m in seen][-12:]}")
