"""Server settings from the environment (SPEC 4, Appendix A). Values are never logged or repr'd.

`load_env(path)` reads a `.env` file tolerantly (unparseable lines are skipped) and lets the real
environment win. `server_settings_from_env(environ)` builds `ServerSettings`; the DeepSeek key
lives only inside `LlmSettings` (private, not repr'd). `/healthz` reports booleans from here.

Public API: `ServerSettings`, `load_env`, `server_settings_from_env`, `DEFAULT_HOST`,
`DEFAULT_PORT`.
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from aidm import __version__
from aidm.dm.llm_settings import LlmSettings, llm_settings_from_env

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_SAVES = Path("saves")
_TRUE = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ServerSettings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    lan: bool = False
    saves_dir: Path = DEFAULT_SAVES
    llm: LlmSettings = field(default_factory=LlmSettings)
    fish_key: bool = False
    fish_voice: bool = False
    tts_enabled: bool = False
    version: str = __version__
    lan_url: str | None = None

    @property
    def fish_ready(self) -> bool:
        return self.fish_key and self.fish_voice


def _present(environ: Mapping[str, str], name: str) -> bool:
    return bool((environ.get(name) or "").strip())


def _port(value: str | None) -> int:
    try:
        port = int(value) if value else DEFAULT_PORT
    except ValueError:
        return DEFAULT_PORT
    return port if 0 < port < 65536 else DEFAULT_PORT


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
        fish_key=_present(environ, "FISH_API_KEY"),
        fish_voice=_present(environ, "FISH_VOICE_ID"),
        tts_enabled=(environ.get("TTS_ENABLED") or "").strip().lower() in _TRUE,
    )
