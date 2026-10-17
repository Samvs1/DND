"""Dice on a wooden table (M26.8). Owner tuning (2026-10-16): "they should resemble hitting wood,
a meaty base with a satisfying finish when the dice finishes rolling", not high and metallic. So an
impact is mostly the table: a low thud (a short falling boom and the board's low modes) and a
wooden knock (noise through a resonant peak at a few hundred Hz), with only a soft contact click on
top. The final settle is the firmest knock, followed by two small rocks on the edge.

A throw is a list of impacts whose gaps shrink geometrically to the final settle at `LAND_S`; the
impact times are returned with the sound, so the screen bounces the die exactly when each knock is
heard (docs/next/GOAL_DICE.md "Repeatable, never boring").

Public API: `LAND_S`, `Impact`, `Die`, `throw`, `clack`.
"""

from dataclasses import dataclass

import numpy as np

from aidm.server.sfxgen.synth import (
    RATE,
    Audio,
    add,
    band,
    modes,
    resonate,
    reverb,
    silence,
    whoosh,
)

LAND_S = 0.85  # the throw's final settle, the moment the stage shows the face
_BODY_F = np.array([64.0, 112.0, 176.0])  # the table's low modes: the meaty thud
_BODY_D = np.array([0.070, 0.050, 0.034])
_TOP_HZ = 4500.0  # nothing bright or metallic above this
# The balance, measured (tests/unit/sfxgen): about half the energy in the thud below 250 Hz, a
# third in the wooden knock (250 Hz - 1 kHz), a tenth of click for a crisp finish, little above.
_THUD = 0.65
_KNOCK = 50.0  # narrow resonant noise is quiet; this lifts it level with the thud
_CLICK = 0.3


@dataclass(frozen=True)
class Impact:
    at: float  # seconds from the start of the sound
    strength: float  # 0..1


def _decay(seconds: float, tau: float) -> Audio:
    return np.exp(-np.arange(int(seconds * RATE)) / (tau * RATE))


class Die:
    """One die on one table: its knock pitch (a few hundred Hz) is set per die, so two dice
    differ, and every impact shifts it a little (the die lands on another edge)."""

    def __init__(self, rng: np.random.Generator, size: float = 1.0) -> None:
        self.rng = rng
        self.knock_hz = float(rng.uniform(420.0, 620.0)) / size
        self.body_f = _BODY_F * rng.uniform(0.95, 1.05, len(_BODY_F))

    def _knock(self, strength: float, scale: float = 1.0) -> Audio:
        rng = self.rng
        n = int(0.06 * RATE)
        hit = rng.normal(0.0, 1.0, n) * _decay(0.06, 0.004)
        low = resonate(hit, self.knock_hz * rng.uniform(0.94, 1.06), 7.0) * _decay(0.06, 0.018)
        mid = resonate(hit, self.knock_hz * 2.3 * rng.uniform(0.95, 1.05), 9.0) * _decay(
            0.06, 0.008
        )
        return (low + 0.35 * mid * (0.5 + strength)) * scale * _KNOCK

    def impact(self, strength: float) -> Audio:
        """One hit of the die on the table: thud (grows with the force), knock and a soft click."""
        rng = self.rng
        x = silence(0.25)
        thud = modes(self.body_f, _BODY_D, np.array([1.0, 0.65, 0.35]), 0.25, rng)
        add(x, thud * strength**1.3 * _THUD, 0.0)
        add(x, self._knock(strength) * 0.55 * strength, 0.0)
        m = int(0.002 * RATE)
        click = band(rng.normal(0.0, 1.0, m), 900, 3200) * np.linspace(1.0, 0.0, m) ** 2
        add(x, click * _CLICK * (0.15 + 0.85 * strength), 0.0)  # soft hits barely click
        return x

    def rattle(self, strength: float) -> Audio:
        """A small knock while the die rolls between bounces: no thud, no click."""
        return self._knock(strength) * 0.32 * strength


def _bounces(rng: np.random.Generator, first: float, land: float) -> list[Impact]:
    hits = int(rng.integers(5, 8))
    gaps = rng.uniform(0.62, 0.74) ** np.arange(hits)
    gaps = gaps / gaps.sum() * (land - first)
    times = first + np.concatenate([[0.0], np.cumsum(gaps)])
    falloff = 0.72 ** np.arange(len(times)) * rng.uniform(0.85, 1.1, len(times))
    strengths = np.clip(falloff, 0.08, 1.0)
    strengths[-1] = max(0.55, float(strengths[-1]) * 2.6)  # the settle: the firm, final knock
    return [
        Impact(round(float(t), 4), round(float(s), 3))
        for t, s in zip(times, strengths, strict=True)
    ]


def _settle(out: Audio, die: Die, at: float, rng: np.random.Generator) -> None:
    """The finish: two small rocks on the edge after the final knock, softer and softer."""
    add(out, die.rattle(0.5), at + float(rng.uniform(0.030, 0.040)), 0.9)
    add(out, die.rattle(0.3), at + float(rng.uniform(0.062, 0.075)), 0.8)


def throw(seed: int, dice: int = 1, land: float = LAND_S) -> tuple[Audio, list[list[Impact]]]:
    """A stage throw of one or two dice: a soft whoosh, a hard first hit, shrinking bounces,
    wooden rolling between them, the settle at `land` and two small rocks on the edge. Returns
    the impacts per die."""
    rng = np.random.default_rng(seed)
    out = silence(land + 0.6)
    add(out, band(whoosh(0.22, 300, 1400, rng), None, 1600), 0.02, 0.04)
    tracks: list[list[Impact]] = []
    for k in range(dice):
        die = Die(rng, size=float(rng.uniform(0.95, 1.05)))
        track = _bounces(rng, float(rng.uniform(0.20, 0.26)) + 0.035 * k, land - 0.012 * k)
        for hit in track:
            add(out, die.impact(hit.strength), hit.at)
        step = float(rng.uniform(0.022, 0.032))
        for t in np.arange(track[1].at + 0.01, track[-1].at - 0.03, step):
            add(out, die.rattle(float(rng.uniform(0.15, 0.35))), float(t + rng.uniform(0, 0.008)))
        _settle(out, die, track[-1].at, rng)
        tracks.append(track)
    return _room(out, rng), tracks


def clack(seed: int) -> tuple[Audio, list[float]]:
    """A combat landing: the die drops by a token, knocks and rocks still. The first hit is at 0."""
    rng = np.random.default_rng(seed)
    die = Die(rng, size=1.1)
    out = silence(0.5)
    times = [
        0.0,
        *(float(rng.uniform(a, b)) for a, b in ((0.07, 0.09), (0.13, 0.15), (0.17, 0.19))),
    ]
    for t, s in zip(times, (0.8, 0.35, 0.18, 0.08), strict=True):
        add(out, die.impact(s), t)
    return _room(out, rng), [round(t, 4) for t in times]


def _room(x: Audio, rng: np.random.Generator) -> Audio:
    """A dark, small room for warmth, and nothing bright left on top."""
    return band(reverb(x, 0.3, 0.12, rng), None, _TOP_HZ)
