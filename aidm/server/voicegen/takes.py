"""Best of several takes, judged on the final word (M13.4d, owner feedback on "Rise.").

Some lines end on one weighty word after a pause ("... I call thee back. [long-break] Rise."). Fish
varies a lot between takes: the word may come out clipped with an upturned pitch, like a question.
A line with `takes: N` is generated N times and the take whose final word is longest, does not
rise in pitch and carries the most weight is kept as the line's cached raw (so `--reprocess` stays
free and reproducible; the candidates are kept next to it for inspection).

- `final_word(audio, rate)`: (start, end) samples of the last voiced region after the last pause of
  at least `MIN_GAP_S`: the 10 ms RMS envelope (relative to its loudest block) smoothed over
  `SMOOTH_S` stays below `FLOOR_DB` (Fish pauses hold breath and room tone at -40..-52 dB with
  short spikes, so an unsmoothed -40 dB gate missed most of them).
- `final_word_features`: `FinalWord(voiced_s, level_db, slope_hz_s, pause_s)`: voiced time of the
  word (YIN frames), its level relative to the speech before it, its pitch slope (linear fit over
  voiced frames; negative = falling, commanding) and the pause before it.
- `take_score`: a take only qualifies when its final word stands alone (pause >= `MIN_PAUSE_S`,
  span <= `MAX_SPAN_S`; otherwise -10, the "word" is really the end of the sentence); then voiced
  time up to `IDEAL_VOICED_S` counts most, a falling or level pitch earns a bonus, an upturn is
  penalised, extra level helps a little. `GOOD_SCORE` marks a take worth keeping.

- A separately generated closing phrase (a line's `parts`, M13.4f: "Rise, once more.") is judged
  by `phrase_features` / `phrase_score`: drawn out, its median pitch near the line's (`ref_f0_hz`;
  neither dull and low nor a high questioning lift) and falling over its last half second.

Public API: `FinalWord`, `final_word`, `final_word_features`, `take_score`, `best_take`,
`GOOD_SCORE`, `Phrase`, `loud_span`, `phrase_features`, `phrase_score`, `best_phrase`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import numpy.typing as npt

from aidm.server.voicegen.analysis import HOP_S, envelope_db, frame_f0

type Audio = npt.NDArray[np.float64]

MIN_GAP_S = 0.25
FLOOR_DB = -35.0
BLOCK_S = 0.010
SMOOTH_S = 0.050
IDEAL_VOICED_S = 1.4
UPTURN_HZ_S = 10.0
END_S = 0.5
MIN_PAUSE_S = 0.20
MAX_SPAN_S = 1.8
GOOD_SCORE = 2.0


@dataclass(frozen=True)
class FinalWord:
    voiced_s: float
    level_db: float
    slope_hz_s: float
    pause_s: float
    span_s: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def _loud(audio: Audio, rate: int) -> npt.NDArray[np.bool_]:
    """Per 10 ms block: is the smoothed envelope above the pause floor?"""
    env = envelope_db(audio, rate, BLOCK_S)
    width = max(1, round(SMOOTH_S / BLOCK_S))
    # Pad with the edge values: zero padding would read as 0 dB (the loudest) at both ends.
    padded = np.pad(env, (width // 2, width - 1 - width // 2), mode="edge")
    smooth = np.convolve(padded, np.ones(width) / width, mode="valid")
    return smooth > FLOOR_DB


def final_word(audio: Audio, rate: int) -> tuple[int, int]:
    """Sample span of the last voiced region after the last long pause (whole clip if none)."""
    loud = _loud(audio, rate)
    idx = np.nonzero(loud)[0]
    if idx.size == 0:
        return 0, audio.size
    last = int(idx[-1])
    gap_blocks = round(MIN_GAP_S / BLOCK_S)
    run, start = 0, 0
    for block in range(last, -1, -1):
        run = 0 if loud[block] else run + 1
        if run >= gap_blocks:
            start = block + run
            break
    block_len = round(BLOCK_S * rate)
    return start * block_len, min(audio.size, (last + 1) * block_len)


def _rms_db(x: Audio) -> float:
    return 10.0 * float(np.log10(np.mean(x**2) + 1e-20))


def final_word_features(audio: Audio, rate: int) -> FinalWord:
    start, end = final_word(audio, rate)
    word = audio[start:end]
    f0 = frame_f0(word, rate)
    voiced = ~np.isnan(f0)
    slope = 0.0
    if voiced.sum() > 3:
        t = np.arange(f0.size) * HOP_S
        slope = float(np.polyfit(t[voiced], f0[voiced], 1)[0])
    body = audio[:start]
    start_block = start // round(BLOCK_S * rate)
    loud = np.nonzero(_loud(audio, rate)[:start_block])[0]
    pause = (start_block - 1 - int(loud[-1])) * BLOCK_S if loud.size else 0.0
    level = _rms_db(word) - _rms_db(body) if body.size else 0.0
    return FinalWord(
        voiced_s=round(float(voiced.sum()) * HOP_S, 2),
        level_db=round(level, 1),
        slope_hz_s=round(slope, 1),
        pause_s=round(pause, 2),
        span_s=round((end - start) / rate, 2),
    )


def take_score(word: FinalWord) -> float:
    if word.pause_s < MIN_PAUSE_S or word.span_s > MAX_SPAN_S:
        return -10.0
    score = 2.0 * min(word.voiced_s, IDEAL_VOICED_S)
    score += 0.3 * min(word.level_db, 3.0)
    if word.slope_hz_s <= UPTURN_HZ_S:
        score += 0.5
    else:
        score -= min(word.slope_hz_s, 150.0) / 50.0
    return round(score, 3)


def best_take(takes: list[tuple[Audio, int]]) -> tuple[int, list[FinalWord]]:
    """Index of the best take and the features of every take (ties keep the earliest)."""
    words = [final_word_features(audio, rate) for audio, rate in takes]
    scores = [take_score(word) for word in words]
    return int(np.argmax(scores)), words


@dataclass(frozen=True)
class Phrase:
    phrase_s: float
    f0_vs_ref_hz: float
    end_slope_hz_s: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def loud_span(audio: Audio, rate: int) -> tuple[int, int]:
    """Samples from the first to the end of the last loud block (the whole clip if none)."""
    loud = np.nonzero(_loud(audio, rate))[0]
    if loud.size == 0:
        return 0, audio.size
    block = round(BLOCK_S * rate)
    return int(loud[0]) * block, min(audio.size, (int(loud[-1]) + 1) * block)


def phrase_features(audio: Audio, rate: int, ref_f0_hz: float) -> Phrase:
    start, end = loud_span(audio, rate)
    f0 = frame_f0(audio[start:end], rate)
    voiced = np.nonzero(~np.isnan(f0))[0]
    median = float(np.median(f0[voiced])) if voiced.size else 0.0
    slope = 0.0
    if voiced.size >= 5:
        tail = voiced[voiced >= voiced[-1] - round(END_S / HOP_S)]
        slope = float(np.polyfit(tail * HOP_S, f0[tail], 1)[0])
    return Phrase(
        phrase_s=round((end - start) / rate, 2),
        f0_vs_ref_hz=round(median - ref_f0_hz, 1) if median else -999.0,
        end_slope_hz_s=round(slope, 1),
    )


def phrase_score(phrase: Phrase) -> float:
    """Drawn out, near the line's pitch (neither dull and low nor a high lift), closing like a
    statement (falling over its last `END_S`)."""
    if phrase.f0_vs_ref_hz <= -999.0:
        return -10.0
    score = 0.5 * min(phrase.phrase_s, 3.0)
    score += 0.8 if phrase.end_slope_hz_s <= 0 else -min(phrase.end_slope_hz_s, 120.0) / 40.0
    score -= abs(min(phrase.f0_vs_ref_hz, 0.0)) / 15.0
    score -= max(phrase.f0_vs_ref_hz - 8.0, 0.0) / 6.0
    return round(score, 3)


def best_phrase(takes: list[tuple[Audio, int]], ref_f0_hz: float) -> tuple[int, list[Phrase]]:
    phrases = [phrase_features(audio, rate, ref_f0_hz) for audio, rate in takes]
    return int(np.argmax([phrase_score(phrase) for phrase in phrases])), phrases
