"""Run the real aidm server in-process on a free port (uvicorn as a task in the caller's loop).

The server shares the event loop with the bots, so reading or scheduling on the table between
awaits is race-free. `SimServer` starts one app (fake LLM by default, the real model with
`live_ai`) over a fresh saves folder, seeded with `new_game_state(seed)`, and captures every
ERROR-level log record (and any record that carries an exception) so the run can fail on
unhandled server errors.

Public API: `SimServer`, `ErrorCapture`, `free_port`.
"""

import asyncio
import logging
import socket
import traceback
from dataclasses import replace
from pathlib import Path

import uvicorn

from aidm.models.state import GameState
from aidm.server.app import create_app
from aidm.server.settings import load_env, server_settings_from_env
from aidm.session.persistence import new_game_state
from aidm.session.table import Table


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class ErrorCapture(logging.Handler):
    """Collects server-side errors: ERROR+ records and anything logged with a traceback."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.errors: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.ERROR and record.exc_info is None:
            return
        text = f"{record.name}: {record.getMessage()}"
        if record.exc_info is not None:
            text += "\n" + "".join(traceback.format_exception(*record.exc_info))
        self.errors.append(text)


class SimServer:
    def __init__(self, seed: int, saves_dir: Path, *, live_ai: bool = False) -> None:
        self.seed = seed
        self.saves_dir = saves_dir
        self.live_ai = live_ai
        self.port = free_port()
        self.capture = ErrorCapture()
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None
        self._table: Table | None = None
        self.state: GameState = new_game_state(seed)

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/ws"

    @property
    def table(self) -> Table:
        assert self._table is not None
        return self._table

    async def start(self) -> None:
        env = load_env() if self.live_ai else {"AIDM_FAKE_LLM": "1"}
        settings = server_settings_from_env(env, port=self.port, saves_dir=self.saves_dir)
        settings = replace(settings, tts_enabled=False)
        if not self.live_ai:
            settings = replace(settings, llm=replace(settings.llm, log_path=None))
        app = create_app(settings, state=self.state)
        self._table = app.state.registry.table
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        logging.getLogger().addHandler(self.capture)
        self._task = asyncio.create_task(self._server.serve())
        for _ in range(150):
            if self._server.started:
                return
            await asyncio.sleep(0.1)
        raise RuntimeError("the simulation server did not start")

    async def stop(self) -> None:
        """Stop the server (the table autosaves on shutdown)."""
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, 30.0)
            except TimeoutError:
                self.capture.errors.append("server shutdown timed out")
        logging.getLogger().removeHandler(self.capture)
