"""TTS providers for the voice build: Fish Audio (WAV, lossless) and an offline fake (M13.3).

`TtsProvider.synthesize(text, voice) -> bytes` returns a WAV file. `FishWavProvider` sends ONE
`fish_audio_sdk.TTSRequest` per line (format wav at `voice.sample_rate`, `reference_id`,
`normalize`, `latency`, prosody speed, temperature, top_p) through the `voice.backend_model`
backend; the SDK is imported lazily, the key lives only in the object (never in repr, logs or
errors: failures raise `VoiceProviderError` with the exception class name only).
`FakeTts` is deterministic: a voiced signal with a known F0 and 1/k harmonics up to 16 kHz in
syllable bursts, plus faint noise for air; it counts its calls so tests can prove no API use.

Public API: `TtsProvider`, `FishWavProvider`, `FakeTts`, `VoiceProviderError`, `read_wav`,
`wav_bytes`.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt
import soundfile as sf

type Audio = npt.NDArray[np.float64]


class VoiceProviderError(RuntimeError):
    """A provider could not produce audio (the message never carries the key)."""


class TtsProvider(Protocol):
    name: str

    def synthesize(self, text: str, voice: Mapping[str, Any]) -> bytes: ...


def read_wav(data: bytes) -> tuple[Audio, int]:
    """WAV bytes -> (mono float64 samples, sample rate); stereo is averaged."""
    samples, rate = sf.read(io.BytesIO(data), dtype="float64", always_2d=True)
    mono = np.asarray(samples, dtype=np.float64).mean(axis=1)
    return mono, int(rate)


def _without_peak_time(data: bytes) -> bytes:
    """Zero the wall-clock timestamp libsndfile puts in a float WAV's PEAK chunk.

    Without this the same samples give different bytes when two writes straddle a second
    (M35.5: a spliced line re-built from cached parts differed from its first build at byte 60).
    """
    out = bytearray(data)
    offset = 12  # after "RIFF" <size> "WAVE"
    while offset + 8 <= len(out):
        size = int.from_bytes(out[offset + 4 : offset + 8], "little")
        if bytes(out[offset : offset + 4]) == b"PEAK" and size >= 8:
            out[offset + 12 : offset + 16] = bytes(4)  # after the chunk header and version
        offset += 8 + size + (size & 1)
    return bytes(out)


def wav_bytes(samples: Audio, rate: int, subtype: str = "PCM_16") -> bytes:
    """Samples -> WAV bytes, the same bytes for the same samples (no write time inside)."""
    buf = io.BytesIO()
    sf.write(buf, samples, rate, format="WAV", subtype=subtype)
    return _without_peak_time(buf.getvalue())


def _import_sdk() -> Any:
    import fish_audio_sdk

    return fish_audio_sdk


@dataclass
class FishWavProvider:
    api_key: str = field(repr=False)
    sdk_loader: Callable[[], Any] = field(default=_import_sdk, repr=False)
    name: str = "fish"

    def synthesize(self, text: str, voice: Mapping[str, Any]) -> bytes:
        if not self.api_key:
            raise VoiceProviderError("FISH_API_KEY is not set")
        try:
            return self._call(text, voice)
        except VoiceProviderError:
            raise
        except Exception as exc:
            status = getattr(exc, "status", None)
            suffix = f" status={status}" if isinstance(status, int) else ""
            raise VoiceProviderError(f"fish tts failed: {type(exc).__name__}{suffix}") from None

    def _call(self, text: str, voice: Mapping[str, Any]) -> bytes:
        sdk = self.sdk_loader()
        session = sdk.Session(self.api_key)
        request = sdk.TTSRequest(
            text=text,
            reference_id=voice["reference_id"],
            format=voice.get("format", "wav"),
            sample_rate=int(voice["sample_rate"]),
            normalize=bool(voice.get("normalize", True)),
            latency=voice.get("latency", "normal"),
            prosody=sdk.Prosody(speed=float(voice.get("prosody_speed", 1.0))),
            temperature=float(voice.get("temperature", 0.7)),
            top_p=float(voice.get("top_p", 0.7)),
        )
        buf = bytearray()
        for chunk in session.tts(request, backend=voice.get("backend_model", "s1")):
            buf.extend(chunk)
        if not buf.startswith(b"RIFF"):
            raise VoiceProviderError("fish tts returned no WAV data")
        return bytes(buf)


@dataclass
class FakeTts:
    f0_hz: float = 140.0
    seconds_per_char: float = 0.02
    max_seconds: float = 2.5
    calls: list[str] = field(default_factory=lambda: [])
    name: str = "fake"

    def synthesize(self, text: str, voice: Mapping[str, Any]) -> bytes:
        self.calls.append(text)
        rate = int(voice.get("sample_rate", 44100))
        seconds = min(self.max_seconds, max(1.2, len(text) * self.seconds_per_char))
        return wav_bytes(synthetic_voice(self.f0_hz, rate, seconds, seed=len(text)), rate)


def synthetic_voice(f0_hz: float, rate: int, seconds: float, seed: int = 0) -> Audio:
    """A voiced test signal: 1/k harmonics of `f0_hz` up to 16 kHz in ~0.3 s syllables."""
    t = np.arange(int(rate * seconds)) / rate
    top = min(16000.0, rate * 0.45)
    tone = np.zeros_like(t)
    for k in range(1, int(top // f0_hz) + 1):
        tone += np.sin(2 * np.pi * f0_hz * k * t + 0.37 * k) / k
    syllable = 0.5 - 0.5 * np.cos(2 * np.pi * t / 0.3)
    gate = (np.floor(t / 0.3) % 4 != 3).astype(np.float64)
    noise = np.random.default_rng(seed).standard_normal(t.size) * 0.004
    voice = tone * syllable * gate
    return 0.5 * voice / np.max(np.abs(voice)) + noise * gate
