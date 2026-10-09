"""Splicing a line's parts into one raw before the chain (M13.4f, owner feedback on "Rise.").

A line with `parts` is built from separately generated pieces (an opening and a closing phrase such
as "Rise, once more."). A plain cut to digital silence is audible (the breath and room tone of the
TTS drop to zero and come back), so the join keeps each clip's own room tone around the cut:
- the earlier piece keeps its speech plus `half` of its natural tail;
- the next piece starts `half` before its speech (its natural lead), is level-matched to the first
  part's speech (+ `gain_db`) and the two overlap in an equal-power crossfade of `XFADE_S` inside
  the pause, so the noise floor never steps; `half` = gap/2 + xfade/2, so the pause is `gap_ms`;
- natural audio missing at a clip edge (a cut close to the speech) is filled by mirroring the
  clip's own available room tone, never with digital silence.
The chain (EQ, compressor, reverb, loudness) then runs over the joined raw, so the reverb flows
across the join. No pitch or time change: samples are only cut, scaled and crossfaded.

Public API: `assemble`, `XFADE_S`, `LEAD_S`, `TAIL_S`.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from aidm.server.voicegen.config import VoicePart
from aidm.server.voicegen.takes import loud_span

type Audio = npt.NDArray[np.float64]

XFADE_S = 0.08
LEAD_S = 0.02  # kept before the first part's speech
TAIL_S = 0.40  # natural audio kept after the last part's speech (the reverb adds its own tail)


def _rms(x: Audio) -> float:
    return float(np.sqrt(np.mean(x**2) + 1e-20))


def _span(clip: Audio, start: int, end: int) -> Audio:
    """clip[start:end]; indices outside the clip are filled by mirroring the available audio."""
    lo, hi = max(start, 0), min(end, clip.size)
    if hi <= lo:
        return np.zeros(max(0, end - start))
    return np.pad(clip[lo:hi], (lo - start, end - hi), mode="symmetric")


def _crossfade(before: Audio, after: Audio, xfade: int) -> Audio:
    ramp = np.sin(np.linspace(0.0, np.pi / 2.0, xfade)) ** 2
    mixed = before[-xfade:] * np.sqrt(1.0 - ramp) + after[:xfade] * np.sqrt(ramp)
    return np.concatenate([before[:-xfade], mixed, after[xfade:]])


def assemble(clips: Sequence[tuple[Audio, int]], parts: Sequence[VoicePart]) -> tuple[Audio, int]:
    """One mono raw from the parts' clips (same sample rate), joined as described above."""
    rate = clips[0][1]
    if any(r != rate for _, r in clips):
        raise ValueError("parts must share one sample rate")
    prev, (start, prev_end) = clips[0][0], loud_span(clips[0][0], rate)
    ref, prev_gain = _rms(prev[start:prev_end]), 1.0
    out = _span(prev, start - round(LEAD_S * rate), prev_end)
    xfade = round(XFADE_S * rate)
    for (clip, _), part in zip(clips[1:], parts[1:], strict=True):
        half = round(part.gap_ms / 2000.0 * rate) + xfade // 2
        tail = _span(prev, prev_end, prev_end + half) * prev_gain
        c_start, c_end = loud_span(clip, rate)
        gain = ref / _rms(clip[c_start:c_end]) * 10 ** (part.gain_db / 20.0)
        head = _span(clip, c_start - half, c_end) * gain
        out = _crossfade(np.concatenate([out, tail]), head, xfade)
        prev, prev_end, prev_gain = clip, c_end, gain
    last = _span(prev, prev_end, prev_end + round(TAIL_S * rate)) * prev_gain
    return np.concatenate([out, last]), rate
