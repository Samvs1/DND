"""Synthesis primitives for the dice sounds (M26.8): damped modes, filters, mixing, a small room,
and the final level. Pure numpy/scipy on mono float64 buffers at `RATE`; nothing here reads or
writes files.

Public API: `RATE`, `Audio`, `silence`, `band`, `resonate`, `modes`, `add`, `whoosh`, `reverb`,
`finish`.
"""

import numpy as np
import numpy.typing as npt
from scipy import signal

type Audio = npt.NDArray[np.float64]

RATE = 48000
_FADE_S = 0.01
_SILENT = 1e-4


def silence(seconds: float) -> Audio:
    return np.zeros(int(seconds * RATE))


def band(x: Audio, lo: float | None, hi: float | None, order: int = 2) -> Audio:
    """A band-pass (both edges), high-pass (lo only) or low-pass (hi only) Butterworth filter."""
    if lo and hi:
        sos = signal.butter(order, [lo, hi], btype="band", fs=RATE, output="sos")
    elif lo:
        sos = signal.butter(order, lo, btype="high", fs=RATE, output="sos")
    else:
        sos = signal.butter(order, hi, btype="low", fs=RATE, output="sos")
    return np.asarray(signal.sosfilt(sos, x), dtype=np.float64)


def resonate(x: Audio, freq: float, q: float) -> Audio:
    """A resonant peak at `freq` (quality `q`): noise through it rings like struck wood."""
    b, a = signal.iirpeak(freq, q, fs=RATE)
    return np.asarray(signal.lfilter(b, a, x), dtype=np.float64)


def modes(
    freqs: npt.ArrayLike,
    decays: npt.ArrayLike,
    amps: npt.ArrayLike,
    seconds: float,
    rng: np.random.Generator,
) -> Audio:
    """A sum of exponentially damped sines (one resonant body), each with a random phase."""
    t = np.arange(int(seconds * RATE)) / RATE
    out = np.zeros_like(t)
    for f, d, a in zip(
        np.atleast_1d(freqs), np.atleast_1d(decays), np.atleast_1d(amps), strict=True
    ):
        phase = rng.uniform(0.0, 2 * np.pi)
        out += a * np.exp(-t / d) * np.sin(2 * np.pi * f * t + phase)
    return out


def add(dst: Audio, src: Audio, at: float, gain: float = 1.0) -> None:
    """Mix `src` into `dst` starting `at` seconds (cut at the end of `dst`)."""
    i = int(at * RATE)
    n = min(len(src), len(dst) - i)
    if n > 0:
        dst[i : i + n] += gain * src[:n]


def whoosh(seconds: float, lo: float, hi: float, rng: np.random.Generator) -> Audio:
    """Air moving: noise swept through a rising band, faded in and out."""
    n = int(seconds * RATE)
    parts = np.array_split(rng.normal(0.0, 1.0, n), 6)
    step = (hi - lo) / 6
    swept = [band(p, lo + step * k, lo + step * (k + 1.5)) for k, p in enumerate(parts)]
    return np.concatenate(swept) * np.sin(np.linspace(0.0, np.pi, n)) ** 2


def reverb(x: Audio, seconds: float, wet: float, rng: np.random.Generator) -> Audio:
    """A small dark room: convolution with decaying, low-passed noise; the tail is kept."""
    n = int(seconds * RATE)
    ir = rng.normal(0.0, 1.0, n) * np.exp(-np.arange(n) / (RATE * seconds / 6))
    ir = band(ir, None, 5000)
    ir /= np.sqrt(np.sum(ir**2))
    tail = np.asarray(signal.fftconvolve(x, ir), dtype=np.float64)
    tail = np.pad(tail, (0, max(0, len(x) + n - len(tail))))[: len(x) + n]
    return np.concatenate([x, np.zeros(n)]) + wet * tail


def finish(x: Audio, rms_db: float, peak_db: float = -1.0) -> Audio:
    """Centre, set the loudness (RMS of the audible part), limit the peak, fade, trim the tail."""
    x = x - np.mean(x)
    loud = np.abs(x) > _SILENT
    if np.any(loud):
        rms = float(np.sqrt(np.mean(x[loud] ** 2)))
        x = x * (10 ** (rms_db / 20) / rms)
    peak = float(np.max(np.abs(x)))
    limit = 10 ** (peak_db / 20)
    if peak > limit:
        x = x * (limit / peak)
    fade = int(_FADE_S * RATE)
    x[-fade:] *= np.linspace(1.0, 0.0, fade)
    audible = np.nonzero(np.abs(x) > _SILENT)[0]
    return x[: audible[-1] + fade] if len(audible) else x
