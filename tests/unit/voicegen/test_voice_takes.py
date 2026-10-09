"""Best of several takes judged on the final word (M13.4d): a clipped, upturned "Rise" loses."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from aidm.server.voicegen.config import parse_config
from aidm.server.voicegen.provider import wav_bytes
from aidm.server.voicegen.runner import fetch_raw, raw_path, reselect
from aidm.server.voicegen.takes import best_take, final_word, final_word_features, take_score
from tests.unit.voicegen.helpers import SR, harmonic_voice, make_paths, small_config


def _glide(f_start: float, f_end: float, seconds: float, amp: float = 0.4) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    f0 = f_start + (f_end - f_start) * t / seconds
    phase = 2.0 * np.pi * np.cumsum(f0) / SR
    out = sum(np.sin(k * phase) / k for k in range(1, 30))
    return amp * out / np.max(np.abs(out))


def _line_then_word(word: np.ndarray, pause_s: float = 0.8) -> np.ndarray:
    body = harmonic_voice(120.0, 1.5)
    return np.concatenate([body, np.zeros(int(SR * pause_s)), word, np.zeros(int(SR * 0.2))])


def test_final_word_is_found_after_the_last_pause() -> None:
    audio = _line_then_word(_glide(130.0, 110.0, 0.9))
    start, end = final_word(audio, SR)
    assert abs(start / SR - 2.3) < 0.05 and abs(end / SR - 3.2) < 0.05


def test_features_tell_a_falling_word_from_an_upturn() -> None:
    falling = final_word_features(_line_then_word(_glide(140.0, 105.0, 1.0)), SR)
    rising = final_word_features(_line_then_word(_glide(110.0, 160.0, 0.3)), SR)
    assert falling.slope_hz_s < -10.0 and rising.slope_hz_s > 10.0
    assert falling.voiced_s > 0.8 and rising.voiced_s < 0.4
    assert abs(falling.pause_s - 0.8) < 0.05
    assert take_score(falling) > take_score(rising)


def test_best_take_prefers_the_long_level_word() -> None:
    clipped = _line_then_word(_glide(110.0, 170.0, 0.25))
    level = _line_then_word(_glide(125.0, 120.0, 1.1))
    short = _line_then_word(_glide(125.0, 118.0, 0.5))
    chosen, words = best_take([(clipped, SR), (level, SR), (short, SR)])
    assert chosen == 1 and len(words) == 3


class _Takes:
    """A provider that returns prepared takes in order and counts calls."""

    name = "takes"

    def __init__(self, takes: list[bytes]) -> None:
        self.takes, self.calls = takes, 0

    def synthesize(self, text: str, voice: Mapping[str, Any]) -> bytes:
        self.calls += 1
        return self.takes[(self.calls - 1) % len(self.takes)]


def test_fetch_raw_keeps_the_best_take_and_caches_it(tmp_path: Path) -> None:
    raw = small_config(takes=3)
    paths = make_paths(tmp_path, raw)
    line = parse_config(raw).lines[0]
    takes = [
        wav_bytes(_line_then_word(_glide(110.0, 170.0, 0.25)), SR),
        wav_bytes(_line_then_word(_glide(125.0, 118.0, 1.1)), SR),
        wav_bytes(_line_then_word(_glide(120.0, 150.0, 0.4)), SR),
    ]
    provider = _Takes(takes)
    data = fetch_raw(paths, line, provider)
    assert provider.calls == 3 and data == takes[1]
    path = raw_path(paths, line)
    assert path.read_bytes() == takes[1]
    assert len(list(paths.raw_dir.glob(f"{path.stem}.take*.wav"))) == 3
    summary = json.loads(path.with_name(f"{path.stem}.takes.json").read_text(encoding="utf-8"))
    assert summary["chosen"] == 1 and len(summary["takes"]) == 3
    assert fetch_raw(paths, line, None) == takes[1] and provider.calls == 3


def test_takes_default_to_one() -> None:
    assert parse_config(small_config()).lines[0].takes == 1


def test_a_word_without_its_own_pause_does_not_qualify() -> None:
    joined = np.concatenate([harmonic_voice(120.0, 1.5), _glide(125.0, 118.0, 1.0)])
    word = final_word_features(joined, SR)
    assert word.pause_s < 0.3 and take_score(word) == -10.0


def test_reselect_picks_again_from_cached_takes_without_the_api(tmp_path: Path) -> None:
    raw = small_config(takes=2)
    paths = make_paths(tmp_path, raw)
    line = parse_config(raw).lines[0]
    path = raw_path(paths, line)
    path.parent.mkdir(parents=True, exist_ok=True)
    weak = wav_bytes(_line_then_word(_glide(110.0, 170.0, 0.25)), SR)
    strong = wav_bytes(_line_then_word(_glide(125.0, 118.0, 1.1)), SR)
    path.with_name(f"{path.stem}.take0.wav").write_bytes(weak)
    path.with_name(f"{path.stem}.take1.wav").write_bytes(strong)
    path.write_bytes(weak)
    picked = reselect(paths, line)
    assert picked is not None and picked[0] == 1 and picked[1] > 2.0
    assert path.read_bytes() == strong
