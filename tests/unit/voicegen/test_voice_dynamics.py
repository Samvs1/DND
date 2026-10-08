"""Compressor, true peak, limiter, loudness and trim (M13.3)."""

import math

import numpy as np

from aidm.server.voicegen.dynamics import (
    compress,
    gain_computer_db,
    limit_true_peak,
    loudness_lufs,
    normalize_loudness,
    trim_tail,
    true_peak_db,
)
from tests.unit.voicegen.helpers import SR, real_chain, rms_db, tone


def _steady_gain_db(amp: float, cfg: dict[str, float]) -> float:
    x = tone(1000.0, 1.5, amp)
    y = compress(x, SR, cfg)
    half = x.size // 2
    return rms_db(y[half:]) - rms_db(x[half:])


def test_compressor_gain_reduction_matches_ratio() -> None:
    cfg = real_chain()["compressor"]
    level = 20.0 * math.log10(0.5)  # a sine of peak 0.5 reads as -6.02 dBFS
    expected = cfg["threshold_db"] + (level - cfg["threshold_db"]) / cfg["ratio"] - level
    assert abs(_steady_gain_db(0.5, cfg) - expected) < 0.3


def test_compressor_slope_above_threshold() -> None:
    cfg = real_chain()["compressor"]
    loud = _steady_gain_db(0.5, cfg)
    louder = _steady_gain_db(1.0, cfg)  # +6.02 dB in -> +6.02 / ratio out
    assert abs((louder - loud) - (-6.02 * (1.0 - 1.0 / cfg["ratio"]))) < 0.3


def test_compressor_leaves_quiet_signal_alone() -> None:
    cfg = real_chain()["compressor"]
    assert abs(_steady_gain_db(0.01, cfg)) < 0.05  # -40 dBFS, far under threshold - knee


def test_soft_knee_is_continuous() -> None:
    levels = np.linspace(-40.0, 0.0, 4001)
    gain = gain_computer_db(levels, -22.0, 2.0, 6.0)
    assert np.max(np.abs(np.diff(gain))) < 0.01
    assert gain.max() <= 0.0


def test_true_peak_sees_intersample_peaks() -> None:
    t = np.arange(SR) / SR
    x = np.sin(2 * np.pi * (SR / 4) * t + math.pi / 4)  # samples at +-0.707, true peak 1.0
    assert abs(20 * math.log10(np.abs(x).max()) + 3.01) < 0.05
    assert abs(true_peak_db(x)) < 0.2


def test_limiter_holds_the_ceiling_and_is_transparent_below() -> None:
    rng = np.random.default_rng(3)
    burst = tone(220.0, 1.0, 0.3) + rng.standard_normal(SR) * 0.02
    burst[SR // 2 : SR // 2 + 400] *= 3.5  # one hot transient
    stereo = np.stack([burst, burst * 0.9], axis=1)
    limited = limit_true_peak(stereo, SR, -1.0)
    assert true_peak_db(limited) <= -1.0
    quiet = stereo * 0.2
    assert np.array_equal(limit_true_peak(quiet, SR, -1.0), quiet)
    assert abs(rms_db(limited[:4000]) - rms_db(stereo[:4000])) < 0.1  # untouched far away


def test_loudness_normalisation_hits_target() -> None:
    x = np.stack([tone(997.0, 3.0, 0.1)] * 2, axis=1)
    y = normalize_loudness(x, SR, -16.0)
    assert abs(loudness_lufs(y, SR) + 16.0) < 0.05


def test_trim_tail_drops_silence_and_fades() -> None:
    x = np.concatenate([tone(440.0, 0.5), np.zeros(SR)])
    y = trim_tail(x, SR, -70.0)
    assert abs(y.size - SR // 2) < 10
    assert abs(y[-1]) < 1e-6
