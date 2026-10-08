"""Dynamics and level stages of the voice chain (M13.3).

- `compress`: feed-forward compressor with an RMS detector over 1 ms blocks, a soft-knee gain
  computer (Giannoulis/Massberg/Reiss 2012), attack/release ballistics on the gain in dB per
  block, and the block gains interpolated back to every sample. No make-up gain (loudness
  normalisation follows). The only Python loop runs over blocks (about 1000 per second).
- `true_peak_db`: ITU-R BS.1770-4 style true peak, 4x oversampled (polyphase), in dBTP.
- `limit_true_peak`: transparent offline look-ahead limiter. A per-sample required gain from the
  4x-oversampled envelope (linked stereo) is min-filtered over +-hold and then box-smoothed over
  +-half the look-ahead; because the box is narrower than the min window, the smoothed gain never
  exceeds the required gain, so no overshoot, and there is no clipping or waveshaping anywhere.
- `normalize_loudness`: one static gain to the target integrated loudness (pyloudnorm, BS.1770).
- `trim_tail`: drops trailing samples below a threshold (dBFS) and fades the last ms out.

Public API: `compress`, `gain_computer_db`, `true_peak_db`, `limit_true_peak`, `loudness_lufs`,
`normalize_loudness`, `trim_tail`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import numpy.typing as npt
import pyloudnorm
from scipy import ndimage, signal

type Audio = npt.NDArray[np.float64]

BLOCK_S = 0.001
LOOKAHEAD_S = 0.005
HOLD_S = 0.040
_EPS = 1e-12


def gain_computer_db(level_db: Audio, threshold: float, ratio: float, knee: float) -> Audio:
    """Static gain change (<= 0 dB) of a soft-knee compressor for the given input levels."""
    over = level_db - threshold
    hard = threshold + over / ratio
    if knee > 0:
        soft = level_db + (1.0 / ratio - 1.0) * (over + knee / 2.0) ** 2 / (2.0 * knee)
    else:
        soft = hard
    out = np.where(2.0 * over < -knee, level_db, np.where(2.0 * over > knee, hard, soft))
    return out - level_db


def _ballistics(target_db: Audio, block_s: float, attack_s: float, release_s: float) -> Audio:
    att = math.exp(-block_s / max(attack_s, 1e-6))
    rel = math.exp(-block_s / max(release_s, 1e-6))
    out = np.empty_like(target_db)
    state = 0.0
    for i, want in enumerate(target_db.tolist()):
        coeff = att if want < state else rel
        state = coeff * state + (1.0 - coeff) * want
        out[i] = state
    return out


def compress(mono: Audio, rate: int, cfg: Mapping[str, Any]) -> Audio:
    block = max(1, round(rate * BLOCK_S))
    count = math.ceil(mono.size / block)
    padded = np.zeros(count * block)
    padded[: mono.size] = mono
    mean_sq = (padded.reshape(count, block) ** 2).mean(axis=1)
    level = 10.0 * np.log10(mean_sq * 2.0 + _EPS)  # +3 dB: a sine's RMS reads as its peak dBFS
    target = gain_computer_db(
        level, float(cfg["threshold_db"]), float(cfg["ratio"]), float(cfg.get("knee_db", 0.0))
    )
    smooth = _ballistics(
        target, block / rate, float(cfg["attack_ms"]) / 1000.0, float(cfg["release_ms"]) / 1000.0
    )
    centres = (np.arange(count) + 0.5) * block
    gain_db = np.interp(np.arange(mono.size), centres, smooth)
    return mono * 10.0 ** (gain_db / 20.0)


def _oversampled(samples: Audio) -> Audio:
    """|x| 4x oversampled, as a (frames, channels) array of the max per original sample."""
    two_d = samples.reshape(samples.shape[0], -1)
    up = signal.resample_poly(two_d, 4, 1, axis=0)
    env = np.abs(np.asarray(up, dtype=np.float64)).reshape(two_d.shape[0], 4, -1).max(axis=1)
    return np.maximum(env, np.abs(two_d))


def true_peak_db(samples: Audio) -> float:
    peak = float(_oversampled(samples).max()) if samples.size else 0.0
    return 20.0 * math.log10(max(peak, _EPS))


def limit_true_peak(samples: Audio, rate: int, ceiling_db: float) -> Audio:
    """Gain-ride `samples` (frames[, channels]) so their 4x true peak stays <= ceiling_db."""
    out = samples
    for margin in (0.1, 0.2, 0.4):
        if true_peak_db(out) <= ceiling_db:
            return out
        ceiling = 10.0 ** ((ceiling_db - margin) / 20.0)
        env = _oversampled(out).max(axis=1)
        need = np.minimum(1.0, ceiling / np.maximum(env, _EPS))
        hold = 2 * round(rate * HOLD_S) + 1
        held = ndimage.minimum_filter1d(need, size=hold, mode="nearest")
        box = 2 * round(rate * LOOKAHEAD_S / 2.0) + 1
        gain = ndimage.uniform_filter1d(held, size=box, mode="nearest")
        out = out * (gain[:, None] if out.ndim == 2 else gain)
    over = true_peak_db(out) - ceiling_db
    return out * 10.0 ** (-max(over, 0.0) / 20.0)


def loudness_lufs(samples: Audio, rate: int) -> float:
    return float(pyloudnorm.Meter(rate).integrated_loudness(samples))


def normalize_loudness(samples: Audio, rate: int, target_lufs: float) -> Audio:
    current = loudness_lufs(samples, rate)
    if not math.isfinite(current):
        return samples
    return samples * 10.0 ** ((target_lufs - current) / 20.0)


def trim_tail(samples: Audio, rate: int, floor_db: float = -70.0, fade_ms: float = 20.0) -> Audio:
    level = np.abs(samples.reshape(samples.shape[0], -1)).max(axis=1)
    loud = np.nonzero(level > 10.0 ** (floor_db / 20.0))[0]
    if loud.size == 0:
        return samples
    out = samples[: int(loud[-1]) + 1].copy()
    fade = min(out.shape[0], max(1, round(rate * fade_ms / 1000.0)))
    ramp = 0.5 + 0.5 * np.cos(np.linspace(0.0, math.pi, fade))
    out[-fade:] = out[-fade:] * (ramp[:, None] if out.ndim == 2 else ramp)
    return out
