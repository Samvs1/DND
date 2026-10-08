"""Synthetic dark hall impulse response, convolution and the wet/dry mix (M13.3).

The IR is deterministic from `reverb.seed` and stereo:
- `predelay_ms` of silence, then a few sparse early reflections in the first 80 ms (random times,
  decaying gains, random signs, per-channel time offsets scaled by `width`, softened by a gentle
  low-pass);
- a diffuse tail of Gaussian noise built in mid/side: L = M + width*S, R = M - width*S with M and S
  independent, so width 0 is mono (correlation 1) and the correlation falls as width grows;
- frequency-dependent decay: the noise is split into 6 bands (<250, 250-500, 500-1k, 1k-2k, 2k-4k,
  >4k Hz), each with an exponential envelope reaching -60 dB at rt60 * BAND_DECAY[band]
  (mids at exactly rt60, higher bands faster), then crossfaded progressively toward a low-pass at
  `damping_hz` (time constant rt60/4), so the tail darkens and smooths as it decays;
- an 8 ms raised-cosine fade-in on the diffuse part and speech-band energy normalisation: the
  mean |H(f)|^2 over 200 Hz - 4 kHz is 1 (a plain unit-energy IR would be louder than unity in the
  voice band, because the dark tail puts its energy low).
Mix rule: equal power. The IR has unit gain in the voice band, so the wet signal carries about the
energy of the dry one, and out = sqrt(1 - wet) * dry + sqrt(wet) * reverb keeps the total level
steady while `wet` sets the wet share of the energy. The dry voice is mono and centred in both
channels.

Public API: `hall_ir`, `convolve_mix`, `MixParts`, `speech_band_gain`, `BAND_EDGES_HZ`,
`BAND_DECAY`, `SPEECH_BAND_HZ`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import signal

type Audio = npt.NDArray[np.float64]

BAND_EDGES_HZ = (250.0, 500.0, 1000.0, 2000.0, 4000.0)
BAND_DECAY = (1.0, 1.0, 1.0, 0.9, 0.7, 0.5)
LN_1000 = math.log(1000.0)
EARLY_TAPS = 6
EARLY_WINDOW_S = 0.080
FADE_IN_S = 0.008
IR_LENGTH_FACTOR = 1.1
SPEECH_BAND_HZ = (200.0, 4000.0)


def _band_filters(rate: int) -> list[npt.NDArray[np.float64]]:
    edges = BAND_EDGES_HZ
    sos = [signal.butter(4, edges[0], "lowpass", fs=rate, output="sos")]
    sos += [
        signal.butter(4, (lo, hi), "bandpass", fs=rate, output="sos")
        for lo, hi in zip(edges[:-1], edges[1:], strict=True)
    ]
    sos.append(signal.butter(4, edges[-1], "highpass", fs=rate, output="sos"))
    return [np.asarray(s, dtype=np.float64) for s in sos]


def _decayed(noise: Audio, t: Audio, rt60: float, rate: int) -> Audio:
    out = np.zeros_like(noise)
    for sos, factor in zip(_band_filters(rate), BAND_DECAY, strict=True):
        band = np.asarray(signal.sosfilt(sos, noise), dtype=np.float64)
        out += band * np.exp(-LN_1000 * t / (rt60 * factor))
    return out


def _darken(tail: Audio, t: Audio, rt60: float, damping_hz: float, rate: int) -> Audio:
    sos = signal.butter(2, min(damping_hz, rate * 0.45), "lowpass", fs=rate, output="sos")
    dark = np.asarray(signal.sosfilt(sos, tail), dtype=np.float64)
    mix = 1.0 - np.exp(-t / (rt60 / 4.0))
    return (1.0 - mix) * tail + mix * dark


def _early(rng: np.random.Generator, pre: int, size: int, width: float, rate: int) -> Audio:
    early = np.zeros((size, 2))
    times = np.sort(rng.uniform(0.005, EARLY_WINDOW_S, EARLY_TAPS))
    signs = rng.choice((-1.0, 1.0), EARLY_TAPS)
    jitter = rng.uniform(-0.0015, 0.0015, (EARLY_TAPS, 2)) * width
    for i, when in enumerate(times):
        gain = 0.6 * math.exp(-when / 0.05) * signs[i]
        for ch in range(2):
            idx = pre + round((when + jitter[i, ch]) * rate)
            if 0 <= idx < size:
                early[idx, ch] += gain
    soft = signal.butter(2, min(9000.0, rate * 0.45), "lowpass", fs=rate, output="sos")
    return np.asarray(signal.sosfilt(soft, early, axis=0), dtype=np.float64)


def hall_ir(cfg: Mapping[str, Any], rate: int) -> Audio:
    """A (frames, 2) unit-energy-per-channel dark hall IR from the `reverb` config."""
    rt60 = float(cfg["rt60_s"])
    width = float(cfg.get("width", 0.5))
    rng = np.random.default_rng(int(cfg.get("seed", 0)))
    pre = round(float(cfg.get("predelay_ms", 0.0)) / 1000.0 * rate)
    tail_len = round(rt60 * IR_LENGTH_FACTOR * rate)
    t = np.arange(tail_len) / rate
    mid = rng.standard_normal(tail_len)
    side = rng.standard_normal(tail_len)
    fade = round(FADE_IN_S * rate)
    ramp = np.ones(tail_len)
    ramp[:fade] = 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, fade))
    ir = np.zeros((pre + tail_len, 2))
    damping = float(cfg.get("damping_hz", 5000.0))
    for ch, sign in enumerate((1.0, -1.0)):
        noise = (mid + sign * width * side) / math.sqrt(1.0 + width * width)
        tail = _darken(_decayed(noise, t, rt60, rate), t, rt60, damping, rate)
        ir[pre:, ch] = tail * ramp
    tail_energy = float(np.sum(ir**2)) / 2.0
    ir = ir / math.sqrt(tail_energy)
    ir += _early(rng, pre, ir.shape[0], width, rate) * 0.5
    return ir / math.sqrt(speech_band_gain(ir, rate))


def speech_band_gain(ir: Audio, rate: int) -> float:
    """Mean |H(f)|^2 of the IR over SPEECH_BAND_HZ, averaged over its channels."""
    power = np.abs(np.fft.rfft(ir, axis=0)) ** 2
    freqs = np.fft.rfftfreq(ir.shape[0], 1.0 / rate)
    band = (freqs >= SPEECH_BAND_HZ[0]) & (freqs <= SPEECH_BAND_HZ[1])
    return float(power[band].mean())


@dataclass(frozen=True)
class MixParts:
    mix: Audio
    dry: Audio
    wet: Audio


def convolve_mix(dry: Audio, ir: Audio, wet: float) -> MixParts:
    """Stereo (frames, 2) equal-power mix of the mono `dry` with its convolution by `ir`.

    The output is len(dry) + len(ir) - 1 frames, so the full tail fits (the dry is zero-padded)."""
    length = dry.size + ir.shape[0] - 1
    reverb = np.stack([signal.fftconvolve(dry, ir[:, ch]) for ch in range(2)], axis=1)
    dry_pad = np.zeros((length, 2))
    dry_pad[: dry.size] = dry[:, None]
    dry_part = math.sqrt(max(0.0, 1.0 - wet)) * dry_pad
    wet_part = math.sqrt(max(0.0, wet)) * np.asarray(reverb, dtype=np.float64)
    return MixParts(mix=dry_part + wet_part, dry=dry_part, wet=wet_part)
