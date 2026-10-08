"""The ONE lossy step of the voice build: 48 kHz stereo float -> mp3 CBR (M13.3).

`encode_mp3` uses ffmpeg (libmp3lame, bit-exact flags, no metadata) when `ffmpeg` is on PATH,
fed a 32-bit float WAV; otherwise the `lameenc` package, fed 16-bit PCM with seeded TPDF dither
(lameenc only takes 16-bit input). Either way nothing lossy precedes it and the target is written
atomically (temp file, then os.replace).

Public API: `encode_mp3`, `encode_ffmpeg`, `encode_lameenc`, `ffmpeg_path`, `Encoder`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import numpy as np
import numpy.typing as npt
import soundfile as sf

type Audio = npt.NDArray[np.float64]
type Encoder = Callable[[Audio, int, int, Path], str]


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _tmp(target: Path, suffix: str) -> Path:
    return target.with_name(f"{target.name}.{os.getpid()}{suffix}")


def encode_ffmpeg(samples: Audio, rate: int, kbps: int, target: Path, exe: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    wav = _tmp(target, ".src.wav")
    mp3 = _tmp(target, ".tmp.mp3")
    try:
        sf.write(wav, samples, rate, format="WAV", subtype="FLOAT")
        cmd = [
            exe,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(wav),
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:a",
            "+bitexact",
            "-c:a",
            "libmp3lame",
            "-b:a",
            f"{kbps}k",
            "-ar",
            str(rate),
            "-f",
            "mp3",
            str(mp3),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        os.replace(mp3, target)
    finally:
        wav.unlink(missing_ok=True)
        mp3.unlink(missing_ok=True)


def encode_lameenc(samples: Audio, rate: int, kbps: int, target: Path) -> None:
    import lameenc

    rng = np.random.default_rng(0)
    lsb = 1.0 / 32768.0
    dither = (rng.uniform(-0.5, 0.5, samples.shape) + rng.uniform(-0.5, 0.5, samples.shape)) * lsb
    pcm = np.clip(np.round((samples + dither) * 32767.0), -32768, 32767).astype("<i2")
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(int(kbps))
    encoder.set_in_sample_rate(int(rate))
    encoder.set_channels(int(samples.shape[1]) if samples.ndim == 2 else 1)
    encoder.set_quality(2)
    data = bytes(encoder.encode(pcm.tobytes())) + bytes(encoder.flush())
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp(target, ".tmp.mp3")
    tmp.write_bytes(data)
    os.replace(tmp, target)


def encode_mp3(samples: Audio, rate: int, kbps: int, target: Path) -> str:
    """Encode and return the encoder used ("ffmpeg" or "lameenc")."""
    exe = ffmpeg_path()
    if exe is not None:
        encode_ffmpeg(samples, rate, kbps, target, exe)
        return "ffmpeg"
    encode_lameenc(samples, rate, kbps, target)
    return "lameenc"
