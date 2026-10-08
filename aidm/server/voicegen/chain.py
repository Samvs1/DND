"""The voice processing chain at 48 kHz float64 (M13.3, docs/next/GOAL_SCRIBE.md "Audio").

Order: resample to `chain.sample_rate` (polyphase, exact rational ratio: 44.1k -> 48k is 160/147;
a sample-rate conversion, never a pitch change) -> high-pass -> warmth -> presence -> air taper
-> compressor -> convolution with the synthetic dark hall IR (the output is long enough for the
full tail) -> wet/dry mix (`reverb.mix_law`, optional `wet_highpass_hz` on the reverb return)
-> loudness to `loudness.target_lufs` -> true-peak limit to `loudness.true_peak_db` -> trim
trailing silence below -70 dBFS with a 20 ms fade, keeping at least `output.tail_ms` after the
dry voice ends. No pitch shift, time stretch, distortion,
bitcrush, chorus or echo stage exists here by design.

Public API: `ProcessResult`, `process`, `resample_to`, `dry_chain`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import signal

from aidm.server.voicegen.dynamics import (
    compress,
    limit_true_peak,
    loudness_lufs,
    normalize_loudness,
    trim_tail,
    true_peak_db,
)
from aidm.server.voicegen.filters import apply_sos, eq_cascade
from aidm.server.voicegen.reverb import convolve_mix, hall_ir

type Audio = npt.NDArray[np.float64]

TRIM_FLOOR_DB = -70.0


@dataclass(frozen=True)
class ProcessResult:
    rate: int
    out: Audio  # (frames, 2), final, ready to encode
    dry: Audio  # mono, after EQ + compressor, before reverb (for F0 and air checks)
    wet_dry_db: float  # energy of the wet part relative to the dry part
    lufs: float
    true_peak_db: float

    @property
    def duration_s(self) -> float:
        return self.out.shape[0] / self.rate


def resample_to(samples: Audio, rate_in: int, rate_out: int) -> Audio:
    if rate_in == rate_out:
        return samples.astype(np.float64)
    ratio = Fraction(rate_out, rate_in)
    out = signal.resample_poly(samples, ratio.numerator, ratio.denominator)
    return np.asarray(out, dtype=np.float64)


def dry_chain(mono: Audio, rate: int, chain: Mapping[str, Any]) -> Audio:
    """EQ cascade then compressor, on a mono signal already at `rate`."""
    return compress(apply_sos(eq_cascade(chain, rate), mono), rate, chain["compressor"])


def _energy_db(part: Audio, ref: Audio) -> float:
    num = float(np.sum(part**2))
    den = float(np.sum(ref**2))
    return 10.0 * float(np.log10(max(num, 1e-20) / max(den, 1e-20)))


def process(raw: Audio, raw_rate: int, chain: Mapping[str, Any]) -> ProcessResult:
    rate = int(chain.get("sample_rate", 48000))
    mono = resample_to(raw, raw_rate, rate)
    dry = dry_chain(mono, rate, chain)
    reverb = chain["reverb"]
    parts = convolve_mix(
        dry,
        hall_ir(reverb, rate),
        float(reverb["wet"]),
        law=str(reverb.get("mix_law", "equal_power")),
        wet_highpass_hz=float(reverb.get("wet_highpass_hz", 0.0)),
        rate=rate,
    )
    loud = chain["loudness"]
    out = normalize_loudness(parts.mix, rate, float(loud["target_lufs"]))
    out = limit_true_peak(out, rate, float(loud["true_peak_db"]))
    keep = dry.size + round(float(chain.get("output", {}).get("tail_ms", 0.0)) / 1000.0 * rate)
    trimmed = trim_tail(out, rate, TRIM_FLOOR_DB)
    if trimmed.shape[0] < min(keep, out.shape[0]):
        trimmed = trim_tail(out[: min(keep, out.shape[0])], rate, -200.0)
    return ProcessResult(
        rate=rate,
        out=trimmed,
        dry=dry,
        wet_dry_db=_energy_db(parts.wet, parts.dry),
        lufs=loudness_lufs(trimmed, rate),
        true_peak_db=true_peak_db(trimmed),
    )
