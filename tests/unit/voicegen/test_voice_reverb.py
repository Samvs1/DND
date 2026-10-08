"""Synthetic dark hall IR and the equal-power mix (M13.3)."""

import math

import numpy as np
from scipy import signal

from aidm.server.voicegen.reverb import convolve_mix, hall_ir, speech_band_gain
from tests.unit.voicegen.helpers import SR, real_chain


def _cfg(**over: float) -> dict[str, float]:
    cfg = dict(real_chain()["reverb"])
    cfg.update(over)
    return cfg


def _band(ir: np.ndarray, lo: float, hi: float) -> np.ndarray:
    sos = signal.butter(4, (lo, hi), "bandpass", fs=SR, output="sos")
    return np.asarray(signal.sosfilt(sos, ir.mean(axis=1)))


def _rt60(x: np.ndarray) -> float:
    """Schroeder backward integration, T30 fit from -5 to -35 dB, extrapolated to 60 dB."""
    edc = np.cumsum((x**2)[::-1])[::-1]
    db = 10 * np.log10(edc / edc[0] + 1e-30)
    i5 = int(np.argmax(db <= -5.0))
    i35 = int(np.argmax(db <= -35.0))
    t = np.arange(i5, i35) / SR
    slope = np.polyfit(t, db[i5:i35], 1)[0]
    return -60.0 / slope


def test_ir_is_deterministic_and_seeded() -> None:
    a = hall_ir(_cfg(), SR)
    assert np.array_equal(a, hall_ir(_cfg(), SR))
    assert not np.array_equal(a, hall_ir(_cfg(seed=8), SR))
    assert a.ndim == 2 and a.shape[1] == 2


def test_ir_length_and_predelay_follow_config() -> None:
    cfg = _cfg()
    ir = hall_ir(cfg, SR)
    seconds = ir.shape[0] / SR
    assert cfg["rt60_s"] <= seconds <= cfg["rt60_s"] * 1.3
    pre = round(cfg["predelay_ms"] / 1000 * SR)
    assert np.abs(ir[: pre - 1]).max() == 0.0


def test_mid_band_decay_matches_rt60() -> None:
    for rt in (1.8, 2.4):
        measured = _rt60(_band(hall_ir(_cfg(rt60_s=rt), SR), 500.0, 1000.0))
        assert abs(measured - rt) / rt < 0.15, (rt, measured)


def test_high_band_decays_faster_than_low_band() -> None:
    ir = hall_ir(_cfg(), SR)
    low = _rt60(_band(ir, 150.0, 300.0))
    high = _rt60(_band(ir, 6000.0, 10000.0))
    assert high < 0.8 * low


def test_width_controls_stereo_correlation() -> None:
    mono = hall_ir(_cfg(width=0.0), SR)
    wide = hall_ir(_cfg(width=0.6), SR)
    assert np.corrcoef(mono[:, 0], mono[:, 1])[0, 1] > 0.99
    assert np.corrcoef(wide[:, 0], wide[:, 1])[0, 1] < 0.8


def test_ir_unit_gain_in_speech_band() -> None:
    assert abs(speech_band_gain(hall_ir(_cfg(), SR), SR) - 1.0) < 1e-9


def test_equal_power_mix() -> None:
    rng = np.random.default_rng(1)
    dry = rng.standard_normal(SR) * 0.1
    ir = hall_ir(_cfg(), SR)
    parts = convolve_mix(dry, ir, 0.3)
    assert parts.mix.shape == (dry.size + ir.shape[0] - 1, 2)
    assert np.allclose(parts.dry[: dry.size, 0], math.sqrt(0.7) * dry)
    assert np.allclose(parts.dry[:, 0], parts.dry[:, 1])  # dry voice mono-centred
    assert np.allclose(parts.mix, parts.dry + parts.wet)
    assert np.array_equal(convolve_mix(dry, ir, 0.0).mix, convolve_mix(dry, ir, 0.0).dry)
