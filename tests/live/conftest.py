"""Shared helpers for the opt-in live tests (RUN_LIVE=1): the environment and a result summary.

The `live_env` fixture merges the gitignored .env (read by name, never printed) with os.environ.
The `live_say` fixture records one ASCII result line per test (mp3 size, audit trail, outcome);
`pytest_terminal_summary` prints every recorded line at the end of the run, so the evidence
is visible even with `-q` (captured stdout of passing tests is not shown).
"""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
LIVE_LINES: list[str] = []


@pytest.fixture
def live_env() -> dict[str, str]:
    values = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    return {**values, **os.environ}


@pytest.fixture
def live_say() -> Callable[[str], None]:
    def say(line: str) -> None:
        text = line.encode("ascii", "replace").decode("ascii")
        LIVE_LINES.append(text)
        print(text)

    return say


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    if not LIVE_LINES:
        return
    terminalreporter.section("live results")
    for line in LIVE_LINES:
        terminalreporter.write_line(line)
