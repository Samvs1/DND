"""The paired-frame pitch check (M13.4): blind to EQ, sharp on a real pitch shift."""

import numpy as np
from scipy.signal import resample_poly

from aidm.server.voicegen.analysis import frame_f0, paired_f0
from aidm.server.voicegen.chain import dry_chain
from aidm.server.voicegen.provider import synthetic_voice
from tests.unit.voicegen.helpers import SR, real_chain


def _gliding_voice(seconds: float = 3.0) -> np.ndarray:
    """A voice whose pitch glides 110 -> 170 Hz, like speech intonation, at SR."""
    t = np.arange(int(SR * seconds)) / SR
    f0 = 110.0 + 60.0 * t / seconds
    phase = 2.0 * np.pi * np.cumsum(f0) / SR
    out = sum(np.sin(k * phase) / k for k in range(1, 40))
    return 0.4 * out / np.max(np.abs(out))


def test_frame_f0_tracks_a_steady_voice() -> None:
    voice = synthetic_voice(140.0, SR, 2.0, seed=4)
    found = frame_f0(voice, SR)
    found = found[~np.isnan(found)]
    assert found.size > 50 and abs(float(np.median(found)) - 140.0) < 1.0


def test_paired_ratio_is_one_through_the_dry_chain() -> None:
    voice = _gliding_voice()
    ratio, agree = paired_f0(voice, dry_chain(voice, SR, real_chain()), SR)
    assert abs(ratio - 1.0) < 0.001 and agree > 0.95


def test_paired_ratio_catches_a_two_percent_pitch_shift() -> None:
    voice = _gliding_voice()
    shifted = resample_poly(voice, 50, 51)  # played back at SR this is 2% higher and 2% shorter
    shifted = np.pad(shifted, (0, voice.size - shifted.size))
    ratio, _ = paired_f0(voice, shifted, SR)
    assert ratio > 1.005


def test_paired_ratio_with_nothing_voiced_is_neutral() -> None:
    silence = np.zeros(SR)
    assert paired_f0(silence, silence, SR) == (1.0, 0.0)
