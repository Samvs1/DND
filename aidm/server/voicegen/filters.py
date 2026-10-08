"""The EQ stages of the voice chain, as second-order sections (M13.3).

- `highpass_sos`: Butterworth high-pass (order, freq from the config).
- `peaking_sos`: RBJ Audio EQ Cookbook peaking biquad; the gain at the centre is exactly gain_db.
- `high_shelf_sos`: RBJ high shelf with slope S (default 1.0, the steepest without overshoot).
  With a negative gain this is the "air taper": half the gain at the corner, the full gain only
  near Nyquist, so the top end is tilted down gently, never cut off like a low-pass.
- `apply_sos` runs a cascade (causal; the phase of these gentle filters is inaudible);
  `response_db` evaluates a cascade's magnitude at given frequencies (for tests and the report).

Public API: `Sos`, `highpass_sos`, `peaking_sos`, `high_shelf_sos`, `apply_sos`, `response_db`,
`eq_cascade`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import signal

type Sos = npt.NDArray[np.float64]
type Audio = npt.NDArray[np.float64]


def _section(b: Sequence[float], a: Sequence[float]) -> Sos:
    a0 = a[0]
    return np.array([[b[0] / a0, b[1] / a0, b[2] / a0, 1.0, a[1] / a0, a[2] / a0]])


def highpass_sos(freq_hz: float, order: int, rate: int) -> Sos:
    sos = signal.butter(int(order), float(freq_hz), btype="highpass", fs=rate, output="sos")
    return np.asarray(sos, dtype=np.float64)


def peaking_sos(freq_hz: float, gain_db: float, q: float, rate: int) -> Sos:
    amp = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * freq_hz / rate
    alpha = math.sin(w0) / (2.0 * q)
    cos = math.cos(w0)
    b = (1.0 + alpha * amp, -2.0 * cos, 1.0 - alpha * amp)
    a = (1.0 + alpha / amp, -2.0 * cos, 1.0 - alpha / amp)
    return _section(b, a)


def high_shelf_sos(freq_hz: float, gain_db: float, rate: int, slope: float = 1.0) -> Sos:
    amp = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * freq_hz / rate
    cos = math.cos(w0)
    alpha = math.sin(w0) / 2.0 * math.sqrt((amp + 1.0 / amp) * (1.0 / slope - 1.0) + 2.0)
    root = 2.0 * math.sqrt(amp) * alpha
    b = (
        amp * ((amp + 1.0) + (amp - 1.0) * cos + root),
        -2.0 * amp * ((amp - 1.0) + (amp + 1.0) * cos),
        amp * ((amp + 1.0) + (amp - 1.0) * cos - root),
    )
    a = (
        (amp + 1.0) - (amp - 1.0) * cos + root,
        2.0 * ((amp - 1.0) - (amp + 1.0) * cos),
        (amp + 1.0) - (amp - 1.0) * cos - root,
    )
    return _section(b, a)


def eq_cascade(chain: Mapping[str, Any], rate: int) -> Sos:
    """high-pass -> warmth -> presence -> air taper, from the resolved chain."""
    hp = chain["highpass"]
    warm = chain["warmth"]
    pres = chain["presence"]
    air = chain["air_taper"]
    return np.vstack(
        [
            highpass_sos(hp["freq_hz"], hp["order"], rate),
            peaking_sos(warm["freq_hz"], warm["gain_db"], warm["q"], rate),
            peaking_sos(pres["freq_hz"], pres["gain_db"], pres["q"], rate),
            high_shelf_sos(air["freq_hz"], air["gain_db"], rate, float(air.get("slope", 1.0))),
        ]
    )


def apply_sos(sos: Sos, samples: Audio) -> Audio:
    return np.asarray(signal.sosfilt(sos, samples), dtype=np.float64)


def response_db(sos: Sos, freqs_hz: Sequence[float], rate: int) -> Audio:
    _, h = signal.sosfreqz(sos, worN=np.asarray(freqs_hz, dtype=np.float64), fs=rate)
    return 20.0 * np.log10(np.maximum(np.abs(h), 1e-12))
