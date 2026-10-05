"""THE text-to-speech adapter: Fish Audio, cached, lazy and fail-soft (SPEC 4 Fish Audio, 11; M8.1).

`FishTts.synthesize(text, tone) -> Path | None` returns the cached mp3 for a sentence, rendering it
through the `fish-audio-sdk` legacy `Session.tts` stream when the cache misses. The SDK is imported
lazily, only on the first real render; with no key or no voice nothing is imported and nothing is
called (zero cost). Any exception or timeout logs the exception class (never a message or key) and
returns None, so the caller shows text only. The file name is the sha1 of `model|voice|tone|text`;
`tts_hook` adapts the adapter to the table's `TtsHook` (a `/tts/<hash>.mp3` URL or None).
The synchronous SDK call runs on a worker thread so the event loop is never blocked.

Public API: `FishSettings`, `fish_settings_from_env`, `FishTts`, `cache_key`, `valid_tts_name`,
`tts_hook`, `DEFAULT_MODEL`, `DEFAULT_CACHE_DIR`.
"""

import asyncio
import hashlib
import logging
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aidm.data.tts_tones import ToneParams, tts_tones
from aidm.models.narration import NarrationTone
from aidm.session.table_core import TtsHook

DEFAULT_MODEL = "s1"
DEFAULT_CACHE_DIR = Path("logs") / "tts_cache"
_NAME = re.compile(r"^[0-9a-f]{40}\.mp3$")
_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class FishSettings:
    api_key: str | None = field(default=None, repr=False)
    voice_id: str | None = field(default=None, repr=False)
    model: str = DEFAULT_MODEL
    voice_name: str | None = None
    cache_dir: Path = DEFAULT_CACHE_DIR
    timeout_s: float = 25.0

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    @property
    def has_voice(self) -> bool:
        return bool(self.voice_id)

    @property
    def ready(self) -> bool:
        return self.has_key and self.has_voice


def fish_settings_from_env(environ: Mapping[str, str]) -> FishSettings:
    def get(name: str) -> str | None:
        return (environ.get(name) or "").strip() or None

    cache = get("TTS_CACHE_DIR")
    return FishSettings(
        api_key=get("FISH_API_KEY"),
        voice_id=get("FISH_VOICE_ID"),
        model=get("FISH_MODEL") or DEFAULT_MODEL,
        voice_name=get("FISH_VOICE_NAME"),
        cache_dir=Path(cache) if cache else DEFAULT_CACHE_DIR,
    )


def cache_key(model: str, voice: str, tone: str, text: str) -> str:
    return hashlib.sha1(f"{model}|{voice}|{tone}|{text}".encode()).hexdigest()


def valid_tts_name(name: str) -> bool:
    return _NAME.fullmatch(name) is not None


def _import_sdk() -> Any:
    import fish_audio_sdk

    return fish_audio_sdk


class FishTts:
    def __init__(
        self, settings: FishSettings, *, sdk_loader: Callable[[], Any] = _import_sdk
    ) -> None:
        self.settings = settings
        self._sdk_loader = sdk_loader
        self._sdk_failed = False

    @property
    def ready(self) -> bool:
        return self.settings.ready and not self._sdk_failed

    def path_for(self, text: str, tone: str) -> Path:
        key = cache_key(self.settings.model, self.settings.voice_id or "", tone, text)
        return self.settings.cache_dir / f"{key}.mp3"

    async def synthesize(self, text: str, tone: NarrationTone | str) -> Path | None:
        clean = text.strip()
        if not clean or not self.ready:
            return None
        name = tone.value if isinstance(tone, NarrationTone) else str(tone)
        path = self.path_for(clean, name)
        if path.is_file():
            return path
        try:
            data = await asyncio.wait_for(
                asyncio.to_thread(self._render, clean, tts_tones().params(name)),
                self.settings.timeout_s,
            )
            if not data:
                _LOG.warning("tts: no audio, text only")
                return None
            self._store(path, data)
        except Exception as exc:
            status = getattr(exc, "status", None)
            _LOG.warning(
                "tts failed: %s%s", type(exc).__name__, f" status={status}" if status else ""
            )
            return None
        return path

    def _render(self, text: str, params: ToneParams) -> bytes:
        try:
            sdk = self._sdk_loader()
        except ImportError:
            self._sdk_failed = True
            _LOG.warning("tts: fish-audio-sdk is not installed, narration stays text only")
            return b""
        session = sdk.Session(self.settings.api_key)
        request = sdk.TTSRequest(
            text=text,
            reference_id=self.settings.voice_id,
            format="mp3",
            prosody=sdk.Prosody(speed=params.speed, volume=params.volume),
            temperature=params.temperature,
        )
        buf = bytearray()
        for chunk in session.tts(request, backend=self.settings.model):
            buf.extend(chunk)
        return bytes(buf)

    @staticmethod
    def _store(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)


def tts_hook(tts: FishTts) -> TtsHook:
    """The table's TTS hook: the `/tts/<hash>.mp3` URL of a sentence, or None."""

    async def hook(text: str, tone: NarrationTone) -> str | None:
        path = await tts.synthesize(text, tone)
        return f"/tts/{path.name}" if path is not None else None

    return hook
