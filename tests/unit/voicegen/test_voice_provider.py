"""Fish WAV request shape and key safety with a stub SDK; the fake TTS; the encoders (M13.3)."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from aidm.server.voicegen.analysis import median_f0
from aidm.server.voicegen.config import load_config
from aidm.server.voicegen.encode import encode_lameenc, encode_mp3
from aidm.server.voicegen.provider import (
    FakeTts,
    FishWavProvider,
    VoiceProviderError,
    read_wav,
    synthetic_voice,
    wav_bytes,
)

KEY = "fish-secret-key-abcdef0123456789"


class StubSdk:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.requests: list[dict[str, Any]] = []
        self.backends: list[str] = []
        self.keys: list[str] = []

    def Session(self, key: str) -> Any:
        self.keys.append(key)
        return SimpleNamespace(tts=self._tts)

    def TTSRequest(self, **kwargs: Any) -> dict[str, Any]:
        self.requests.append(kwargs)
        return kwargs

    def Prosody(self, **kwargs: Any) -> dict[str, Any]:
        return kwargs

    def _tts(self, request: dict[str, Any], backend: str) -> Any:
        if self.fail:
            raise RuntimeError(f"401 bad key {KEY}")
        self.backends.append(backend)
        yield wav_bytes(synthetic_voice(140.0, request["sample_rate"], 1.0), 44100)


def test_fish_request_is_wav_with_config_settings() -> None:
    voice = load_config().voice
    sdk = StubSdk()
    data = FishWavProvider(api_key=KEY, sdk_loader=lambda: sdk).synthesize("Hello.", voice)
    request = sdk.requests[0]
    assert request["format"] == "wav" and request["sample_rate"] == voice["sample_rate"]
    assert request["reference_id"] == voice["reference_id"]
    assert request["latency"] == voice["latency"] and request["normalize"] is True
    assert request["prosody"] == {"speed": voice["prosody_speed"]}
    assert request["temperature"] == voice["temperature"] and request["top_p"] == voice["top_p"]
    assert sdk.backends == [voice["backend_model"]] and sdk.keys == [KEY]
    assert data.startswith(b"RIFF")


def test_fish_errors_and_repr_never_carry_the_key() -> None:
    provider = FishWavProvider(api_key=KEY, sdk_loader=lambda: StubSdk(fail=True))
    assert KEY not in repr(provider)
    with pytest.raises(VoiceProviderError) as info:
        provider.synthesize("Hello.", load_config().voice)
    assert KEY not in str(info.value) and "RuntimeError" in str(info.value)
    assert info.value.__cause__ is None


def test_fake_tts_has_known_f0_and_counts_calls() -> None:
    fake = FakeTts(f0_hz=120.0, max_seconds=1.5)
    raw, rate = read_wav(fake.synthesize("Some text.", {"sample_rate": 44100}))
    assert rate == 44100 and fake.calls == ["Some text."]
    assert abs(median_f0(raw, rate) - 120.0) / 120.0 < 0.01


def _stereo() -> np.ndarray:
    voice = synthetic_voice(140.0, 48000, 1.0) * 0.5
    return np.stack([voice, voice], axis=1)


def test_mp3_encoders_write_once_atomically(tmp_path: Path) -> None:
    target = tmp_path / "out" / "a.mp3"
    used = encode_mp3(_stereo(), 48000, 320, target)
    assert used in ("ffmpeg", "lameenc") and target.stat().st_size > 10000
    other = tmp_path / "b.mp3"
    encode_lameenc(_stereo(), 48000, 320, other)
    assert other.stat().st_size > 10000
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["a.mp3", "b.mp3"]


def test_float_wav_bytes_carry_no_write_time() -> None:
    """libsndfile stamps a float WAV's PEAK chunk with the wall clock; wav_bytes zeroes it."""
    samples = np.linspace(-0.5, 0.5, 1000).astype(np.float32).astype(np.float64)  # exact in FLOAT
    data = wav_bytes(samples, 48000, subtype="FLOAT")
    peak = data.index(b"PEAK")
    assert data[peak + 12 : peak + 16] == bytes(4)
    assert np.array_equal(read_wav(data)[0], samples)
    assert wav_bytes(samples, 48000, subtype="FLOAT") == data
