"""Server settings from the environment (SPEC 4, Appendix A). Values are never logged or repr'd.

`load_env(path)` reads a `.env` file tolerantly (unparseable lines are skipped) and lets the real
environment win. `server_settings_from_env(environ)` builds `ServerSettings`; the DeepSeek key
lives only inside `LlmSettings` and the Fish key inside `FishSettings` (private, not repr'd).
`/healthz` reports booleans from here.

`AIDM_AI_TURN_PAUSE` (seconds, 0..5, default 1.5): how long the shared screen holds each monster
turn so the table can follow it (M20.3, owner choice). `AIDM_SHOW_WAIT_CAP` (seconds, 0..20,
default 8): the longest an AI turn or a hero's turn clock waits for the shared screen to finish
showing the rolls before it (M26.3).

Public API: `ServerSettings`, `load_env`, `server_settings_from_env`, `DEFAULT_HOST`,
`DEFAULT_PORT`, `DEFAULT_AI_TURN_PAUSE_S`, `DEFAULT_SHOW_WAIT_CAP_S`.
"""

import logging
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from aidm import __version__
from aidm.dm.llm_settings import LlmSettings, llm_settings_from_env
from aidm.server.tts import FishSettings, fish_settings_from_env

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_SAVES = Path("saves")
DEFAULT_AI_TURN_PAUSE_S = 1.5
MAX_AI_TURN_PAUSE_S = 5.0
DEFAULT_SHOW_WAIT_CAP_S = 8.0
MAX_SHOW_WAIT_CAP_S = 20.0
_TRUE = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ServerSettings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    lan: bool = False
    saves_dir: Path = DEFAULT_SAVES
    llm: LlmSettings = field(default_factory=LlmSettings)
    fish: FishSettings = field(default_factory=FishSettings)
    tts_enabled: bool = False
    version: str = __version__
    lan_url: str | None = None
    https: bool = False
    web_root: Path | None = None  # AIDM_WEB_ROOT: serve a copy of aidm/web (tests, art-less runs)
    ai_turn_pause_s: float = DEFAULT_AI_TURN_PAUSE_S
    show_wait_cap_s: float = DEFAULT_SHOW_WAIT_CAP_S

    @property
    def fish_ready(self) -> bool:
        return self.fish.ready


def _port(value: str | None) -> int:
    try:
        port = int(value) if value else DEFAULT_PORT
    except ValueError:
        return DEFAULT_PORT
    return port if 0 < port < 65536 else DEFAULT_PORT


def _seconds(value: str | None, default: float, top: float) -> float:
    try:
        seconds = float(value) if value else default
    except ValueError:
        return default
    return default if math.isnan(seconds) else min(max(seconds, 0.0), top)


def _web_root(value: str | None) -> Path | None:
    return Path(value) if value and value.strip() else None


def load_env(path: Path | None = None) -> dict[str, str]:
    """The `.env` file merged under the process environment (the environment wins)."""
    merged: dict[str, str] = {}
    target = path if path is not None else Path(".env")
    if target.is_file():
        logging.getLogger("dotenv.main").setLevel(logging.ERROR)
        try:
            values = dotenv_values(target)
        except (OSError, UnicodeDecodeError):
            values = {}
        merged.update({k: v for k, v in values.items() if v is not None})
    merged.update(os.environ)
    return merged


def server_settings_from_env(
    environ: Mapping[str, str],
    *,
    lan: bool = False,
    host: str | None = None,
    port: int | None = None,
    saves_dir: Path | None = None,
) -> ServerSettings:
    bind = host or environ.get("AIDM_HOST") or DEFAULT_HOST
    if lan and host is None:
        bind = "0.0.0.0"
    return ServerSettings(
        host=bind,
        port=port if port is not None else _port(environ.get("AIDM_PORT")),
        lan=lan,
        saves_dir=saves_dir if saves_dir is not None else DEFAULT_SAVES,
        llm=llm_settings_from_env(environ),
        fish=fish_settings_from_env(environ),
        web_root=_web_root(environ.get("AIDM_WEB_ROOT")),
        tts_enabled=(environ.get("TTS_ENABLED") or "").strip().lower() in _TRUE,
        ai_turn_pause_s=_seconds(
            environ.get("AIDM_AI_TURN_PAUSE"), DEFAULT_AI_TURN_PAUSE_S, MAX_AI_TURN_PAUSE_S
        ),
        show_wait_cap_s=_seconds(
            environ.get("AIDM_SHOW_WAIT_CAP"), DEFAULT_SHOW_WAIT_CAP_S, MAX_SHOW_WAIT_CAP_S
        ),
    )
