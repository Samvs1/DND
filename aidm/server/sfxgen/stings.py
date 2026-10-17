"""The synthesised verdict stings (failure, a natural 1) and the board's hit and miss (M26.8):
failure is a dull thud and a muted falling third, a natural 1 a crack and a dissonant drone. The
good news (success, a natural 20) is built on a real recording: aidm/server/sfxgen/payoff.py.

Public API: `failure`, `natural_1`, `hit`, `miss`.
"""

import numpy as np

from aidm.server.sfxgen.synth import RATE, Audio, add, band, modes, reverb, silence, whoosh

_NOTE = {"A2": 110.0, "Bb2": 116.54, "D3": 146.83, "F3": 174.61}


def _pad(freqs: list[float], seconds: float, attack: float) -> Audio:
    t = np.arange(int(seconds * RATE)) / RATE
    env = np.minimum(t / attack, 1.0) * np.exp(-np.maximum(t - attack, 0.0) / (seconds * 0.35))
    x = np.zeros_like(t)
    for f in freqs:
        x += np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
    return x * env


def _boom(seconds: float, f0: float, f1: float) -> Audio:
    t = np.arange(int(seconds * RATE)) / RATE
    freq = f1 + (f0 - f1) * np.exp(-t / 0.05)
    return np.sin(2 * np.pi * np.cumsum(freq) / RATE) * np.exp(-t / (seconds * 0.3))


def failure(seed: int) -> Audio:
    """A dull low thud and a muted falling third."""
    rng = np.random.default_rng(seed)
    out = silence(1.6)
    add(out, _boom(0.6, 120, 55), 0.0, 0.45)
    for i, note in enumerate(("F3", "D3")):
        add(out, band(_pad([_NOTE[note]], 1.1, 0.02), None, 900), 0.06 + 0.22 * i, 0.22)
    n = int(0.5 * RATE)
    hush = band(rng.normal(0.0, 1.0, n), 200, 900) * np.exp(-np.arange(n) / (0.08 * RATE))
    add(out, hush, 0.0, 0.06)
    return reverb(out, 1.0, 0.18, rng)


def natural_1(seed: int) -> Audio:
    """The die cracks: a crackle burst, a low boom and a dissonant fading drone."""
    rng = np.random.default_rng(seed)
    out = silence(2.0)
    n = int(0.35 * RATE)
    crack = np.zeros(n)
    for _ in range(40):
        i = int(rng.integers(0, n - 200))
        crack[i : i + 60] += rng.normal(0.0, 1.0, 60) * rng.uniform(0.3, 1.0)
    add(out, band(crack, 1800, 7000) * np.exp(-np.arange(n) / (0.07 * RATE)), 0.0, 0.7)
    add(out, _boom(0.7, 90, 40), 0.0, 0.5)
    t = np.arange(int(1.6 * RATE)) / RATE
    drone = (np.sin(2 * np.pi * _NOTE["A2"] * t) + np.sin(2 * np.pi * _NOTE["Bb2"] * t)) * np.exp(
        -t / 0.6
    )
    add(out, band(drone, None, 600), 0.08, 0.16)
    return reverb(out, 1.2, 0.2, rng)


def hit(seed: int, crit: bool = False) -> Audio:
    """A short low thump with a crunch; a critical hit adds a bright metallic ring."""
    rng = np.random.default_rng(seed)
    out = silence(0.9 if crit else 0.5)
    add(out, _boom(0.35, 110, 55), 0.0, 0.7)
    n = int(0.12 * RATE)
    add(
        out,
        band(rng.normal(0.0, 1.0, n), 250, 2200) * np.exp(-np.arange(n) / (0.025 * RATE)),
        0.0,
        0.5,
    )
    if crit:
        ring = modes(
            [1210, 1870, 2730, 3920], [0.45, 0.3, 0.2, 0.12], [0.5, 0.35, 0.25, 0.15], 0.8, rng
        )
        add(out, ring, 0.01, 0.35)
    return reverb(out, 0.5, 0.1, rng)


def miss(seed: int) -> Audio:
    """A blade whooshing through air."""
    return whoosh(0.32, 500, 2600, np.random.default_rng(seed))
