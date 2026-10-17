"""The good-news stings (M26.8), both built on the real CC0 recording (aidm/server/sfxgen/impact.py)
and both raised +3 semitones (owner pick 2026-10-17, "a bit more magical"). The owner signs off on
exact sounds, so each is ONE file that always plays the same (never alternated or pitch-varied).

- `success`: the shaped impact, a deep boom, a rumble, a glint and an airy shimmer; mono.
- `natural_20`: one 3.0 s stereo sound in two parts: an ignite (a short swell, a whoomp, a flash,
  then a riser while the bonuses add up) and, from 1.05 s, a triumph (the riser sucked in, the
  biggest hit, gold sparkle and dust) that fades out from 2.7 s. The stage show is choreographed to
  it: `natural_20_beats` measures its beats from the audio (dice_timing.json `natural_20`), so a
  new sound re-times the show.

Public API: `SEMITONES`, `success`, `natural_20`, `natural_20_beats`.
"""

import numpy as np
from scipy import signal

from aidm.server.sfxgen.grains import glint, gold_dust, riser, shimmer, sparkle_burst
from aidm.server.sfxgen.impact import (
    crack,
    cut_to,
    drum_body,
    impact_source,
    pitched,
    rumble,
    shape_impact,
    small_room,
    sub_boom,
    swell_in,
)
from aidm.server.sfxgen.synth import RATE, Audio, add, band, silence

SEMITONES = 3
_LEAD = 0.2  # the natural 20's swell before the ignite hit
_HIT = 0.26  # the slam's place in the triumph part (a reversed swell leads into it)
_TRIUMPH_AT = 1.05  # where the triumph part starts
_END = 3.0
_FADE = 0.3
_CHIME_HZ = 3055.0  # the recording rings this short tone ~0.6 s after its hit (measured at +0)


def _lift() -> float:
    return 2 ** (SEMITONES / 12)


def success() -> Audio:
    """The verdict sting for a passed check or save (the catalog sets its level)."""
    rng = np.random.default_rng(900)
    lift = _lift()
    out = silence(2.4)
    add(out, shape_impact(pitched(impact_source(), SEMITONES)), 0.0, 0.7)
    add(out, sub_boom(1.3), 0.09, 0.75)
    add(out, rumble(rng, 1.5, 0.5), 0.09, 0.3)
    add(out, glint(rng, lift), 0.85, 0.5)
    add(out, shimmer(1.2, rng, lift, 60), 0.82, 0.14)
    return cut_to(small_room(out, 1.1, 0.3, rng), 2.6)


def _ignite(rng: np.random.Generator, lift: float) -> Audio:
    out = silence(3.0)
    add(out, swell_in(shimmer(_LEAD + 0.03, rng, lift, 40), _LEAD), 0.0, 0.45)
    t = np.arange(int(0.35 * RATE)) / RATE
    whoomp = band(rng.normal(0, 1, len(t)), 250, 2500) * np.minimum(t / 0.012, 1.0)
    add(out, whoomp * np.exp(-t / 0.07), _LEAD, 0.5)
    add(out, sub_boom(0.7, f_end=58.0, f_start=120.0, tau=0.16), _LEAD + 0.01, 0.7)
    add(out, glint(rng, lift, 0.18), _LEAD + 0.005, 1.2)
    add(out, sparkle_burst(0.6, rng, lift, 90), _LEAD + 0.02, 0.22)
    add(out, riser(2.75, rng, lift), _LEAD + 0.05, 0.32)
    return cut_to(small_room(out, 0.4, 0.08, rng), 3.0, fade=0.4)


def _triumph(up: Audio, rng: np.random.Generator, lift: float) -> Audio:
    out = silence(2.6)
    add(out, swell_in(shimmer(_HIT + 0.05, rng, lift, 60), _HIT), 0.0, 0.5)
    add(out, band(swell_in(shape_impact(up)[: int(0.6 * RATE)], _HIT), None, 7000), 0.0, 0.4)
    add(out, shape_impact(up, swell=0.02), _HIT, 0.85)
    add(out, sub_boom(1.6, f_end=42.0, f_start=105.0, tau=0.42), _HIT + 0.01, 1.1)
    add(out, drum_body(), _HIT, 0.7)
    add(out, crack(rng), _HIT, 0.5)
    add(out, glint(rng, lift, 0.2), _HIT + 0.005, 1.4)
    add(out, sparkle_burst(1.0, rng, lift, 170), _HIT + 0.02, 0.34)
    add(out, gold_dust(1.85, rng, lift), _HIT + 0.12, 0.3)
    out = np.tanh(2.2 * out / np.max(np.abs(out))) / np.tanh(2.2)  # denser: the hit lands harder
    return cut_to(small_room(out, 0.5, 0.1, rng), 2.2, fade=0.32)


def _stereo(left: Audio, right: Audio, rms_db: float) -> Audio:
    """The impact and booms are the same in both ears and the grains differ (width); the level
    follows the middle, the peak stays under -1 dB, the last 30 ms fade."""
    n = max(len(left), len(right))
    left, right = (np.pad(c - np.mean(c), (0, n - len(c))) for c in (left, right))
    mid = 0.5 * (left + right)
    gain = 10 ** (rms_db / 20) / np.sqrt(np.mean(mid[np.abs(mid) > 1e-4] ** 2))
    peak = max(np.max(np.abs(left)), np.max(np.abs(right))) * gain
    gain *= min(1.0, 10 ** (-1 / 20) / peak)
    out = np.stack([left * gain, right * gain], axis=1)
    fade = int(0.03 * RATE)
    out[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    return out


def natural_20() -> Audio:
    """The natural 20 as one stereo sound, 3.0 s, peak at -1 dB."""
    lift = _lift()
    up = pitched(impact_source(), SEMITONES)
    ig = [_ignite(np.random.default_rng(960 + 17 * ch), lift) for ch in (0, 1)]
    tr = [_triumph(up, np.random.default_rng(970 + 31 * ch), lift) for ch in (0, 1)]
    ignite, triumph = _stereo(ig[0], ig[1], -21.0), _stereo(tr[0], tr[1], -18.0)
    mix = np.zeros((int(_END * RATE), 2))
    gain = np.ones(len(ignite))
    at, under = int(_TRIUMPH_AT * RATE), int(_HIT * RATE)
    gain[at : at + under] = np.linspace(1.0, 0.0, under)  # the riser is sucked into the slam
    gain[at + under :] = 0.0
    n = min(len(ignite), len(mix))
    mix[:n] += ignite[:n] * gain[:n, None]
    m = min(len(triumph), len(mix) - at)
    mix[at : at + m] += triumph[:m]
    fade = int(_FADE * RATE)
    mix[-fade:] *= (np.linspace(1.0, 0.0, fade) ** 2)[:, None]
    return mix * (10 ** (-1 / 20) / np.max(np.abs(mix)))


def _onset_strength(x: Audio) -> tuple[Audio, Audio]:
    """Spectral flux (5 ms steps): how much new sound starts at each moment."""
    _, t, spec = signal.stft(x, RATE, nperseg=1024, noverlap=1024 - 240)
    mag = np.log1p(np.abs(spec) * 50)
    flux = np.maximum(np.diff(mag, axis=1), 0).sum(axis=0)
    flux = np.convolve(flux, np.hanning(5) / np.hanning(5).sum(), mode="same")
    return np.asarray(t[1:], dtype=np.float64), np.asarray(flux, dtype=np.float64)


def _chime(x: Audio, slam: float) -> float:
    """Where the recording's own ring starts after the slam: its band's loudest 10 ms, walked back
    while within 10 dB of that peak."""
    hz = _CHIME_HZ * _lift()
    sos = signal.butter(4, [hz * 0.92, hz * 1.08], btype="bandpass", fs=RATE, output="sos")
    ring = np.asarray(signal.sosfiltfilt(sos, x), dtype=np.float64)
    hop = int(0.01 * RATE)
    first, last = int((slam + 0.3) / 0.01), int((slam + 0.8) / 0.01)
    frames = (ring[i * hop : (i + 1) * hop] for i in range(first, last))
    level = [10 * np.log10(np.mean(f**2) + 1e-18) for f in frames]
    k = int(np.argmax(level))
    peak = level[k]
    while k > 0 and level[k - 1] >= peak - 10:
        k -= 1
    return (first + k) * 0.01


def natural_20_beats(audio: Audio) -> dict[str, float]:
    """The moments the natural 20 show lands on, measured from its sound: the ignite hit (flare)
    and the slam (the strongest onsets before and after 0.6 s), the recording's own ring (the
    spark), where its fade starts and its end."""
    x = audio.mean(axis=1) if audio.ndim == 2 else audio
    t, flux = _onset_strength(x)
    early, late = t < 0.6, (t >= 0.6) & (t < 2.0)
    flare = float(t[early][np.argmax(flux[early])])
    slam = float(t[late][np.argmax(flux[late])])
    return {
        "flare": round(flare, 3),
        "slam": round(slam, 3),
        "chime": round(_chime(x, slam), 3),
        "fade": round(_END - _FADE, 3),
        "end": _END,
    }
