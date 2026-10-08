"""Measurements for the voice report (M13.3): F0, air, tail (the session cannot listen).

- `median_f0`: YIN (de Cheveigne and Kawahara 2002): difference function via FFT, cumulative
  mean normalised difference, absolute threshold 0.15 then the local minimum, parabolic
  interpolation, on 40 ms frames every 20 ms whose level is within 35 dB of the loudest frame;
  the median over voiced frames. Raw and processed must agree within 1% (no pitch shift).
- `high_band_db`: energy above 10 kHz relative to the total energy, in dB.
- `tail_s`: time from the end of the dry voice to where the output's 10 ms RMS envelope falls
  below -60 dB relative to its loudest block.

Public API: `median_f0`, `high_band_db`, `tail_s`, `envelope_db`.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

type Audio = npt.NDArray[np.float64]

F0_MIN_HZ = 60.0
F0_MAX_HZ = 400.0
FRAME_S = 0.040
HOP_S = 0.020
GATE_DB = 35.0
YIN_THRESHOLD = 0.15
YIN_MAX_ACCEPT = 0.35
CHUNK = 128


def _frames(mono: Audio, size: int, hop: int) -> Audio:
    if mono.size < size:
        return np.zeros((0, size))
    count = 1 + (mono.size - size) // hop
    idx = np.arange(size)[None, :] + hop * np.arange(count)[:, None]
    return mono[idx]


def _cmndf(frames: Audio, window: int, max_lag: int) -> Audio:
    n_fft = 1 << int(math.ceil(math.log2(frames.shape[1] + window)))
    spec = np.fft.rfft(frames, n_fft, axis=1)
    head = np.fft.rfft(frames[:, :window], n_fft, axis=1)
    corr = np.fft.irfft(spec * np.conj(head), n_fft, axis=1)[:, : max_lag + 1]
    sq = np.concatenate([np.zeros((frames.shape[0], 1)), np.cumsum(frames**2, axis=1)], axis=1)
    lags = np.arange(max_lag + 1)
    energy_tau = sq[:, lags + window] - sq[:, lags]
    diff = sq[:, [window]] + energy_tau - 2.0 * corr
    diff[:, 0] = 0.0
    running = np.cumsum(diff[:, 1:], axis=1) / lags[None, 1:]
    out = np.ones_like(diff)
    out[:, 1:] = diff[:, 1:] / np.maximum(running, 1e-12)
    return out


def _pick(curve: Audio, min_lag: int) -> float | None:
    below = np.nonzero(curve[min_lag:-1] < YIN_THRESHOLD)[0]
    if below.size:
        tau = int(below[0]) + min_lag
        while tau + 1 < curve.size - 1 and curve[tau + 1] < curve[tau]:
            tau += 1
    else:
        tau = int(np.argmin(curve[min_lag:-1])) + min_lag
        if curve[tau] > YIN_MAX_ACCEPT:
            return None
    left, mid, right = curve[tau - 1], curve[tau], curve[tau + 1]
    denom = left - 2.0 * mid + right
    shift = 0.5 * (left - right) / denom if abs(denom) > 1e-12 else 0.0
    return tau + float(np.clip(shift, -1.0, 1.0))


def median_f0(mono: Audio, rate: int) -> float:
    """Median F0 (Hz) over voiced frames, or 0.0 when nothing is voiced."""
    window = round(FRAME_S * rate)
    max_lag = math.ceil(rate / F0_MIN_HZ)
    min_lag = max(2, math.floor(rate / F0_MAX_HZ))
    frames = _frames(mono, window + max_lag + 1, round(HOP_S * rate))
    if frames.shape[0] == 0:
        return 0.0
    level = 10.0 * np.log10(np.mean(frames[:, :window] ** 2, axis=1) + 1e-20)
    frames = frames[level >= level.max() - GATE_DB]
    found: list[float] = []
    for start in range(0, frames.shape[0], CHUNK):
        curves = _cmndf(frames[start : start + CHUNK], window, max_lag)
        for curve in curves:
            tau = _pick(curve, min_lag)
            if tau is not None and tau > 0:
                found.append(rate / tau)
    return float(np.median(found)) if found else 0.0


def high_band_db(mono: Audio, rate: int, split_hz: float = 10000.0) -> float:
    power = np.abs(np.fft.rfft(mono)) ** 2
    freqs = np.fft.rfftfreq(mono.size, 1.0 / rate)
    high = float(power[freqs >= split_hz].sum())
    return 10.0 * math.log10(max(high, 1e-20) / max(float(power.sum()), 1e-20))


def envelope_db(samples: Audio, rate: int, block_s: float = 0.010) -> Audio:
    """10 ms RMS envelope (mono sum of channels) in dB relative to its loudest block."""
    mono = samples.reshape(samples.shape[0], -1).mean(axis=1)
    block = max(1, round(rate * block_s))
    count = mono.size // block
    rms = np.sqrt(np.mean(mono[: count * block].reshape(count, block) ** 2, axis=1))
    db = 20.0 * np.log10(rms + 1e-12)
    return db - db.max()


def tail_s(out: Audio, dry: Audio, rate: int, floor_db: float = -60.0) -> float:
    block_s = 0.010
    env_out = envelope_db(out, rate, block_s)
    env_dry = envelope_db(dry, rate, block_s)
    out_end = int(np.nonzero(env_out > floor_db)[0][-1]) if env_out.size else 0
    dry_end = int(np.nonzero(env_dry > floor_db)[0][-1]) if env_dry.size else 0
    return max(0, out_end - dry_end) * block_s
