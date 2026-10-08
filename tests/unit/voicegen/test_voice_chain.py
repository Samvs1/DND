"""The whole chain on synthetic signals (M13.3): no pitch shift, loudness, true peak, air."""

import numpy as np
import pytest

from aidm.server.voicegen.analysis import high_band_db, median_f0, tail_s
from aidm.server.voicegen.chain import ProcessResult, dry_chain, process, resample_to
from aidm.server.voicegen.provider import synthetic_voice
from tests.unit.voicegen.helpers import SR, harmonic_voice, real_chain

RAW_SR = 44100


@pytest.fixture(scope="module")
def voiced() -> tuple[np.ndarray, ProcessResult]:
    raw = synthetic_voice(140.0, RAW_SR, 3.0, seed=2)
    return raw, process(raw, RAW_SR, real_chain())


def test_resample_44k1_to_48k_keeps_f0() -> None:
    raw = harmonic_voice(140.0, 1.0, RAW_SR)
    up = resample_to(raw, RAW_SR, SR)
    assert abs(up.size - SR) <= 1
    assert abs(median_f0(up, SR) - 140.0) / 140.0 < 0.001


def test_no_pitch_shift_through_the_chain(voiced: tuple[np.ndarray, ProcessResult]) -> None:
    raw, result = voiced
    f0_raw = median_f0(raw, RAW_SR)
    f0_dry = median_f0(result.dry, result.rate)
    assert abs(f0_raw - 140.0) / 140.0 < 0.01
    assert abs(f0_dry - f0_raw) / f0_raw < 0.01


def test_output_loudness_and_true_peak(voiced: tuple[np.ndarray, ProcessResult]) -> None:
    _, result = voiced
    loud = real_chain()["loudness"]
    assert result.rate == 48000
    assert result.out.ndim == 2 and result.out.shape[1] == 2
    assert abs(result.lufs - loud["target_lufs"]) < 0.5
    assert result.true_peak_db <= loud["true_peak_db"]


def test_tail_kept_and_trimmed(voiced: tuple[np.ndarray, ProcessResult]) -> None:
    raw, result = voiced
    assert result.duration_s > raw.size / RAW_SR + 0.9  # at least tail_ms of reverb kept
    assert 0.5 < tail_s(result.out, result.dry, result.rate) < 3.0
    assert np.abs(result.out[-1]).max() < 1e-6


def test_wet_share_follows_config(voiced: tuple[np.ndarray, ProcessResult]) -> None:
    _, result = voiced
    reverb = real_chain()["reverb"]
    wet = reverb["wet"]
    # Energy ratio: the gains enter squared for the linear law, once for equal power.
    power = 20 if reverb.get("mix_law", "equal_power") == "linear" else 10
    expected = power * np.log10(wet / (1 - wet))
    # The return high-pass removes some reverb energy on top, so the wet share sits at or below it.
    assert expected - 4.0 < result.wet_dry_db < expected + 3.0


def test_air_kept_by_the_dry_chain() -> None:
    rng = np.random.default_rng(5)
    broadband = rng.standard_normal(SR * 2) * 0.05
    out = dry_chain(broadband, SR, real_chain())
    assert high_band_db(broadband, SR) - high_band_db(out, SR) < 4.0


def test_no_pitch_shift_on_a_harmonic_voice_at_48k() -> None:
    raw = harmonic_voice(140.0, 2.0)
    result = process(raw, SR, real_chain())
    assert abs(median_f0(result.dry, SR) - 140.0) / 140.0 < 0.01
