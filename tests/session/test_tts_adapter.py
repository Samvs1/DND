"""The Fish adapter with a fake SDK: cache, disabled, fail-soft, tone prosody, /tts route (M8.1)."""

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.testclient import TestClient

from aidm.data.tts_tones import load_tts_tones
from aidm.models.narration import NarrationTone
from aidm.server.tts import (
    FishSettings,
    FishTts,
    cache_key,
    fish_settings_from_env,
    tts_hook,
    valid_tts_name,
)
from tests.session.server_fixtures import make_app

MP3 = b"ID3" + b"\x00" * 64


class FakeSdk:
    def __init__(self, chunks: list[bytes] | None = None, error: Exception | None = None) -> None:
        self.calls: list[tuple[Any, str]] = []
        self.chunks = [MP3] if chunks is None else chunks
        self.error = error
        outer = self

        class Session:
            def __init__(self, key: str) -> None:
                self.key = key

            def tts(self, request: Any, backend: str = "") -> Any:
                outer.calls.append((request, backend))
                if outer.error is not None:
                    raise outer.error
                yield from outer.chunks

        self.Session = Session
        self.TTSRequest = SimpleNamespace
        self.Prosody = SimpleNamespace


def make(tmp_path: Path, sdk: FakeSdk, **over: Any) -> FishTts:
    base: dict[str, Any] = {
        "api_key": "k-test",
        "voice_id": "v-test",
        "model": "m-test",
        "cache_dir": tmp_path / "cache",
    }
    return FishTts(FishSettings(**{**base, **over}), sdk_loader=lambda: sdk)


async def test_synthesize_writes_mp3_and_cache_hit_skips_the_call(tmp_path: Path) -> None:
    sdk = FakeSdk()
    tts = make(tmp_path, sdk)
    first = await tts.synthesize("The door creaks open.", NarrationTone.EXPLORATION)
    assert first is not None and first.read_bytes() == MP3
    assert (
        first.name == f"{cache_key('m-test', 'v-test', 'exploration', 'The door creaks open.')}.mp3"
    )
    second = await tts.synthesize("The door creaks open.", NarrationTone.EXPLORATION)
    assert second == first and len(sdk.calls) == 1
    other = await tts.synthesize("The door creaks open.", NarrationTone.COMBAT)
    assert other != first and len(sdk.calls) == 2
    assert sdk.calls[0][1] == "m-test"


async def test_disabled_returns_none_without_importing(tmp_path: Path) -> None:
    def boom() -> Any:
        raise AssertionError("the SDK must not be imported")

    for settings in (
        FishSettings(cache_dir=tmp_path),
        FishSettings(api_key="k", cache_dir=tmp_path),
        FishSettings(voice_id="v", cache_dir=tmp_path),
    ):
        assert await FishTts(settings, sdk_loader=boom).synthesize("Hi.", "social") is None
    assert not (tmp_path / "x").exists()
    sys.modules.pop("fish_audio_sdk", None)
    off = FishTts(FishSettings(cache_dir=tmp_path))
    assert await off.synthesize("Hi.", "social") is None
    assert "fish_audio_sdk" not in sys.modules


async def test_blank_text_is_not_synthesized(tmp_path: Path) -> None:
    sdk = FakeSdk()
    assert await make(tmp_path, sdk).synthesize("   ", "social") is None
    assert sdk.calls == []


async def test_exception_returns_none_and_logs_without_secrets(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    class Rejected(Exception):
        status = 401

    tts = make(tmp_path, FakeSdk(error=Rejected("key k-test rejected")))
    assert await tts.synthesize("Hello there.", "social") is None
    assert "Rejected" in caplog.text and "401" in caplog.text
    assert "k-test" not in caplog.text and "v-test" not in caplog.text
    assert not (tmp_path / "cache").exists()


async def test_empty_stream_and_timeout_return_none(tmp_path: Path) -> None:
    assert await make(tmp_path, FakeSdk(chunks=[])).synthesize("Hello.", "social") is None

    class Slow(FakeSdk):
        def __init__(self) -> None:
            super().__init__()
            outer = self

            class Session:
                def __init__(self, key: str) -> None: ...

                def tts(self, request: Any, backend: str = "") -> Any:
                    import time

                    time.sleep(0.5)
                    outer.calls.append((request, backend))
                    yield MP3

            self.Session = Session

    assert await make(tmp_path, Slow(), timeout_s=0.05).synthesize("Hello.", "social") is None


async def test_missing_sdk_goes_quiet_after_one_attempt(tmp_path: Path) -> None:
    attempts: list[int] = []

    def missing() -> Any:
        attempts.append(1)
        raise ImportError("nope")

    tts = FishTts(FishSettings(api_key="k", voice_id="v", cache_dir=tmp_path), sdk_loader=missing)
    assert await tts.synthesize("One.", "social") is None
    assert await tts.synthesize("Two.", "social") is None
    assert len(attempts) == 1


async def test_tone_prosody_mapping(tmp_path: Path) -> None:
    sdk = FakeSdk()
    tts = make(tmp_path, sdk)
    await tts.synthesize("Fight now.", NarrationTone.COMBAT)
    await tts.synthesize("Speak softly.", NarrationTone.SOCIAL)
    await tts.synthesize("Walk on.", NarrationTone.EXPLORATION)
    await tts.synthesize("Unknown tone.", "mystery")
    speeds = [(c[0].prosody.speed, c[0].temperature) for c in sdk.calls]
    assert speeds == [(1.12, 0.85), (0.95, 0.55), (1.0, 0.7), (1.0, 0.7)]
    request = sdk.calls[0][0]
    assert request.format == "mp3" and request.reference_id == "v-test"
    tones = load_tts_tones()
    assert tones.params("combat").speed > tones.params("exploration").speed
    assert tones.params("social").speed < tones.params("exploration").speed
    assert tones.params("").speed == 1.0 and tones.params(None).speed == 1.0


async def test_hook_returns_url_or_none(tmp_path: Path) -> None:
    tts = make(tmp_path, FakeSdk())
    url = await tts_hook(tts)("A line.", NarrationTone.SOCIAL)
    assert url is not None and url.startswith("/tts/") and url.endswith(".mp3")
    assert (
        await tts_hook(make(tmp_path, FakeSdk(chunks=[])))("Other.", NarrationTone.SOCIAL) is None
    )


def test_settings_from_env_hide_the_key() -> None:
    settings = fish_settings_from_env(
        {"FISH_API_KEY": "secret-xyz", "FISH_VOICE_ID": "v1", "FISH_MODEL": "s2-pro"}
    )
    assert settings.ready and settings.model == "s2-pro"
    assert "secret-xyz" not in repr(settings)
    assert fish_settings_from_env({}).model == "s1" and not fish_settings_from_env({}).ready


def test_hash_name_validation() -> None:
    good = "a" * 40 + ".mp3"
    assert valid_tts_name(good)
    for bad in (
        "a" * 39 + ".mp3",
        "A" * 40 + ".mp3",
        "a" * 40,
        "../" + "a" * 40 + ".mp3",
        "g" * 40 + ".mp3",
    ):
        assert not valid_tts_name(bad)


def test_tts_route_serves_cached_files_only(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    name = cache_key("m", "v", "social", "Hi.") + ".mp3"
    (cache / name).write_bytes(MP3)
    (tmp_path / "secret.mp3").write_bytes(b"no")
    app = make_app(tmp_path, {"TTS_CACHE_DIR": str(cache)})
    with TestClient(app) as client:
        ok = client.get(f"/tts/{name}")
        assert ok.status_code == 200 and ok.content == MP3
        assert ok.headers["content-type"] == "audio/mpeg"
        assert client.get(f"/tts/{'b' * 40}.mp3").status_code == 404
        assert client.get("/tts/notahash.mp3").status_code == 404
        assert client.get("/tts/..%2Fsecret.mp3").status_code == 404
        assert client.get(f"/tts/{name.upper()}").status_code == 404
