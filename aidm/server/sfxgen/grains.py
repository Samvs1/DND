"""Grain layers for the success and natural 20 stings (M26.8): airy sparkle built from many tiny
grains of filtered noise, never one pitch (the owner rejected bells, brass and single high chimes).
`lift` is the pitch ratio of the impact under the layer: every grain moves up with it (the owner's
pick is +3 semitones, "a bit more magical"). Seeded through `rng`; the order of the draws is part
of the sound, so keep it.

Public API: `glint`, `shimmer`, `sparkle_burst`, `riser`, `gold_dust`.
"""

import numpy as np

from aidm.server.sfxgen.synth import RATE, Audio, add, band, silence

_TOP = 15000.0  # no grain band reaches past this (the mp3 keeps up to 16 kHz)


def _t(seconds: float) -> Audio:
    return np.arange(int(seconds * RATE)) / RATE


def _fade_out(x: Audio, seconds: float) -> Audio:
    n = min(len(x), int(seconds * RATE))
    x = x.copy()
    x[-n:] *= np.linspace(1.0, 0.0, n) ** 2
    return x


def glint(rng: np.random.Generator, lift: float, seconds: float = 0.12) -> Audio:
    """A short bright flash of noise (a struck spark), 3 to 9 kHz."""
    t = _t(seconds)
    noise = band(rng.normal(0, 1, len(t)), 3000 * lift, min(9000 * lift, _TOP))
    return noise * np.minimum(t / 0.004, 1.0) * np.exp(-t / 0.035)


def shimmer(seconds: float, rng: np.random.Generator, lift: float, density: int = 60) -> Audio:
    """An airy sparkle with no single pitch: tiny grains of bright noise and faint tones."""
    out = silence(seconds)
    for _ in range(density):
        at = rng.uniform(0, seconds * 0.7)
        n = int(rng.uniform(0.02, 0.06) * RATE)
        grain = band(rng.normal(0, 1, n), 2200 * lift, min(7500 * lift, _TOP)) * np.hanning(n)
        add(out, grain, at, rng.uniform(0.2, 0.6) * np.exp(-at / (seconds * 0.4)))
        if rng.random() < 0.3:
            f = rng.uniform(1400, 3200) * lift
            tone = np.sin(2 * np.pi * f * _t(0.25)) * np.exp(-_t(0.25) / 0.06)
            add(out, tone, at, 0.05)
    return out


def sparkle_burst(seconds: float, rng: np.random.Generator, lift: float, density: int) -> Audio:
    """A dense burst of bright grains whose pitch climbs as it thins out (triumphant, no echo)."""
    out = silence(seconds)
    for _ in range(density):
        u = rng.random() ** 1.4  # most grains early
        at = u * seconds * 0.75
        n = int(rng.uniform(0.015, 0.045) * RATE)
        lo = (2000 + 3500 * u) * lift
        grain = band(rng.normal(0, 1, n), lo, min(lo * 2.2, _TOP)) * np.hanning(n)
        add(out, grain, at, rng.uniform(0.3, 0.8) * (1 - 0.7 * u))
    return out


def riser(seconds: float, rng: np.random.Generator, lift: float, climb: float = 0.75) -> Audio:
    """Tension while the bonuses add up: grains that climb in pitch and grow denser over a low hum
    rising with them; it levels off after `climb` seconds."""
    out = silence(seconds)
    for _ in range(420):
        at = rng.uniform(0, seconds - 0.06)
        u = min(at / climb, 1.0)
        if rng.random() > 0.25 + 0.75 * u:
            continue
        n = int(rng.uniform(0.02, 0.05) * RATE)
        lo = (900 + 3600 * u) * lift
        grain = band(rng.normal(0, 1, n), lo, min(lo * 1.9, _TOP)) * np.hanning(n)
        add(out, grain, at, rng.uniform(0.25, 0.6) * (0.5 + 0.5 * u))
    rise = np.minimum(_t(seconds) / climb, 1.0)
    ph = 2 * np.pi * np.cumsum(46 + 26 * rise**1.3) / RATE
    hum = (np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)) * (0.25 + 0.75 * rise**1.5)
    add(out, hum, 0.0, 0.35)
    return _fade_out(out, 0.4)


def gold_dust(seconds: float, rng: np.random.Generator, lift: float) -> Audio:
    """Fine bright grains hanging in the air while the banner holds, thinning out slowly."""
    out = silence(seconds)
    for _ in range(220):
        at = rng.uniform(0, seconds * 0.92)
        n = int(rng.uniform(0.012, 0.035) * RATE)
        lo = rng.uniform(4500, 7000) * lift
        grain = band(rng.normal(0, 1, n), lo, min(lo * 1.7, _TOP)) * np.hanning(n)
        add(out, grain, at, rng.uniform(0.2, 0.7) * (1 - 0.5 * at / seconds))
    return out
