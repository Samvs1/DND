"""The real recording under the success and natural 20 stings (M26.8) and its shaping. The owner
rejected every synthesised payoff (bells, brass, crisp chimes) and picked a real CC0 sound:
"magicProjectile_impact" by rafaelzimrp (Freesound 570855, CC0 1.0, data/sfx/SOURCES.md), shaped
after the owner's BG3 reference: the sharp attack softened into a short swell, the very top eased,
the boxy mids trimmed, a deep boom under it and a small room around it.

Public API: `SOURCE`, `impact_source`, `pitched`, `shape_impact`, `sub_boom`, `rumble`,
`drum_body`, `crack`, `swell_in`, `small_room`, `cut_to`.
"""

from functools import cache
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from aidm.server.sfxgen.synth import RATE, Audio, band, reverb

SOURCE = Path(__file__).resolve().parents[3] / "data" / "sfx" / "magic_projectile_impact.flac"


def _t(seconds: float) -> Audio:
    return np.arange(int(seconds * RATE)) / RATE


def _fade_out(x: Audio, seconds: float = 0.1) -> Audio:
    n = min(len(x), int(seconds * RATE))
    x = x.copy()
    x[-n:] *= np.linspace(1.0, 0.0, n) ** 2
    return x


@cache
def _source(path: Path) -> Audio:
    data, rate = sf.read(str(path), dtype="float64", always_2d=True)
    x = np.asarray(data.mean(axis=1), dtype=np.float64)
    if rate != RATE:
        x = np.asarray(resample_poly(x, RATE, rate), dtype=np.float64)
    env = np.abs(x)
    x = x[max(0, int(np.argmax(env > env.max() * 0.05)) - int(0.005 * RATE)) :]  # from its onset
    return x / np.max(np.abs(x))


def impact_source(path: Path = SOURCE) -> Audio:
    """The recording from its onset, peak at 1 (read once)."""
    return _source(path).copy()


def pitched(x: Audio, semitones: float) -> Audio:
    """The same sound played faster and higher (resampled, not processed)."""
    if not semitones:
        return x
    return np.asarray(resample_poly(x, 1000, int(round(1000 * 2 ** (semitones / 12)))))


def shape_impact(x: Audio, swell: float = 0.06) -> Audio:
    """Soften the attack into a short swell, ease the very top, trim the boxy mids a little."""
    t = np.arange(len(x)) / RATE
    x = x * np.minimum(t / swell, 1.0) ** 1.5
    return x - 0.45 * band(x, 6500, None) - 0.25 * band(x, 380, 900)


def sub_boom(
    seconds: float, f_end: float = 57.0, f_start: float = 78.0, tau: float = 0.38
) -> Audio:
    """A deep falling boom with two harmonics (they carry it on TV speakers)."""
    t = _t(seconds)
    freq = f_end + (f_start - f_end) * np.exp(-t / 0.05)
    ph = 2 * np.pi * np.cumsum(freq) / RATE
    body = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
    return _fade_out(body * np.minimum(t / 0.006, 1.0) * np.exp(-t / tau))


def rumble(rng: np.random.Generator, seconds: float, tau: float) -> Audio:
    t = _t(seconds)
    low = band(rng.normal(0, 1, len(t)), 30, 120, order=3)
    return _fade_out(low * np.minimum(t / 0.03, 1.0) * np.exp(-t / tau))


def drum_body() -> Audio:
    """A low drum's body under the natural 20's slam: a few low modes, a quick pitch settle."""
    t = _t(0.6)
    out = np.zeros_like(t)
    for f, amp, tau in ((72.0, 1.0, 0.32), (116.0, 0.5, 0.2), (168.0, 0.3, 0.12)):
        ph = 2 * np.pi * np.cumsum(f * (1 + 0.25 * np.exp(-t / 0.03))) / RATE
        out += amp * np.sin(ph) * np.exp(-t / tau)
    return _fade_out(out * np.minimum(t / 0.003, 1.0))


def crack(rng: np.random.Generator) -> Audio:
    t = _t(0.04)
    return band(rng.normal(0, 1, len(t)), 1500, 11000) * np.exp(-t / 0.006)


def swell_in(x: Audio, seconds: float) -> Audio:
    """The last `seconds` of `x` reversed and ramped up: it is sucked into what comes next."""
    x = x[::-1][-int(seconds * RATE) :]
    return x * np.linspace(0.0, 1.0, len(x)) ** 1.6


def small_room(x: Audio, seconds: float, wet: float, rng: np.random.Generator) -> Audio:
    """A small warm room: the reverb's tail only, low-passed, under the dry sound."""
    dry = np.concatenate([x, np.zeros(int(seconds * RATE))])
    return dry + wet * band(reverb(x, seconds, 1.0, rng) - dry, None, 6000)


def cut_to(x: Audio, seconds: float, fade: float = 0.5) -> Audio:
    """End the sound by `seconds` on a soft fade (a room tail would ring on for ages)."""
    x = x[: int(seconds * RATE)].copy()
    n = int(fade * RATE)
    x[-n:] *= np.linspace(1.0, 0.0, n) ** 2
    return x
