"""M33.2 ultrareview finding 10 (docs/reviews/M33_ultrareview.md): a stalling Fish render must
never take threads from the loop's shared default executor (DNS and httpx for the LLM use it).
Renders run on the adapter's own small pool; a full pool means text only; a render that ends
after its waiter gave up still fills the cache; the SDK's HTTP client gets a read timeout.
Fake SDK only (the adapter's `sdk_loader`): Fish is never called."""

import asyncio
import dataclasses
import logging
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from aidm.server.tts import FishSettings, FishTts, fish_settings_from_env

MP3 = b"ID3" + b"\x00" * 64


class GatedSdk:
    """A fake SDK whose render blocks until `gate` is set; it records the rendering threads."""

    def __init__(self) -> None:
        self.gate = threading.Event()
        self.threads: list[str] = []
        self.clients: list[httpx.Client] = []
        outer = self

        class Session:
            def __init__(self, key: str) -> None:
                self._sync_client = httpx.Client()
                outer.clients.append(self._sync_client)

            def tts(self, request: Any, backend: str = "") -> Any:
                outer.threads.append(threading.current_thread().name)
                outer.gate.wait(5)
                yield MP3

        self.Session = Session
        self.TTSRequest = SimpleNamespace
        self.Prosody = SimpleNamespace


def _make(tmp_path: Path, sdk: GatedSdk, **over: Any) -> FishTts:
    base: dict[str, Any] = {"api_key": "k", "voice_id": "v", "cache_dir": tmp_path / "cache"}
    return FishTts(FishSettings(**{**base, **over}), sdk_loader=lambda: sdk)


async def _until(check: Any) -> None:
    for _ in range(200):
        if check():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition never held")


async def test_v1_m33_tts_renders_off_the_default_executor(tmp_path: Path) -> None:
    sdk = GatedSdk()
    sdk.gate.set()
    tts = _make(tmp_path, sdk)
    try:
        assert await tts.synthesize("The gate holds.", "social") is not None
        assert sdk.threads and all(name.startswith("tts") for name in sdk.threads)
        assert sdk.clients[0].timeout.read == tts.settings.timeout_s  # the SDK's client timeout
    finally:
        tts.close()


async def test_v1_m33_tts_full_pool_is_text_only(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Two stalled renders fill the pool: the next sentences skip synthesis at once (logged
    once), and the stalled renders still store their audio when they finish."""
    sdk = GatedSdk()
    tts = _make(tmp_path, sdk, timeout_s=0.05, render_workers=2)
    try:
        stalled = [await tts.synthesize(f"Line {i}.", "social") for i in range(2)]
        assert stalled == [None, None]
        with caplog.at_level(logging.WARNING, logger="aidm.server.tts"):
            started = time.monotonic()
            skipped = [await tts.synthesize(f"Busy {i}.", "social") for i in range(3)]
            assert skipped == [None, None, None] and time.monotonic() - started < 0.1
        await _until(lambda: len(sdk.threads) == 2)
        await asyncio.sleep(0.05)
        assert len(sdk.threads) == 2  # no third render was queued
        assert caplog.text.count("busy") == 1
        sdk.gate.set()
        await _until(lambda: all(tts.path_for(f"Line {i}.", "social").is_file() for i in (0, 1)))
        assert await tts.synthesize("Line 0.", "social") == tts.path_for("Line 0.", "social")
        tts.settings = dataclasses.replace(tts.settings, timeout_s=5.0)
        assert await tts.synthesize("Busy 0.", "social") is not None  # the pool is free again
        assert len(sdk.threads) == 3
    finally:
        sdk.gate.set()
        tts.close()


async def test_v1_m33_tts_disabled_starts_no_threads(tmp_path: Path) -> None:
    before = threading.active_count()
    tts = FishTts(FishSettings(cache_dir=tmp_path))
    assert await tts.synthesize("Quiet.", "social") is None
    assert threading.active_count() == before
    tts.close()


def test_v1_m33_tts_workers_setting() -> None:
    assert FishSettings().render_workers == 2
    assert fish_settings_from_env({"TTS_RENDER_WORKERS": "3"}).render_workers == 3
    assert fish_settings_from_env({"TTS_RENDER_WORKERS": "lots"}).render_workers == 2
    assert fish_settings_from_env({"TTS_RENDER_WORKERS": "0"}).render_workers == 1
