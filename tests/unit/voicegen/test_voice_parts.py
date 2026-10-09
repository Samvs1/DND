"""Lines spliced from separately recorded parts (M13.4f): seamless join, shared parts, picks."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from aidm.data.scribe_lines import ScribeLine
from aidm.server.voicegen.config import parse_config
from aidm.server.voicegen.parts import LEAD_S, TAIL_S, assemble
from aidm.server.voicegen.provider import read_wav, wav_bytes
from aidm.server.voicegen.runner import fetch_raw, has_raw
from aidm.server.voicegen.takes import best_phrase
from tests.unit.voicegen.helpers import SR, harmonic_voice, make_paths, small_config


def _noise_floor(seconds: float, db: float = -65.0, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, 10 ** (db / 20.0), int(SR * seconds))


def _clip(voice: np.ndarray, lead_s: float = 0.3, tail_s: float = 0.5) -> np.ndarray:
    """A TTS-like clip: room tone, speech, room tone."""
    out = _noise_floor(lead_s + voice.size / SR + tail_s, seed=voice.size)
    start = int(lead_s * SR)
    out[start : start + voice.size] += voice
    return out


def _glide(f_start: float, f_end: float, seconds: float) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    phase = 2.0 * np.pi * np.cumsum(f_start + (f_end - f_start) * t / seconds) / SR
    out = sum(np.sin(k * phase) / k for k in range(1, 30))
    return 0.4 * out / np.max(np.abs(out))


def _parts_config(gap_ms: float = 400.0, **second: Any) -> dict[str, Any]:
    raw = small_config()
    raw["lines"][0].pop("text")
    raw["lines"][0]["parts"] = [
        {"text": "[calm] From the final page."},
        {"text": "[warm] Rise, once more.", "gap_ms": gap_ms, **second},
    ]
    return raw


def test_parts_join_text_and_hash_their_settings() -> None:
    line = parse_config(_parts_config()).lines[0]
    assert line.text == "[calm] From the final page. [warm] Rise, once more."
    assert [part.gap_ms for part in line.parts] == [0.0, 400.0]
    other = parse_config(_parts_config(gap_ms=600.0)).lines[0]
    assert line.chain_sha != other.chain_sha and line.text_sha == other.text_sha
    shown = ScribeLine.model_validate({"id": "x.1", "group": "revive", "parts": line_parts_raw()})
    assert shown.display == "From the final page. Rise, once more."


def line_parts_raw() -> list[dict[str, str]]:
    return [{"text": "[calm] From the final page."}, {"text": "[warm] Rise, once more."}]


def test_assemble_keeps_the_pause_and_never_drops_to_silence() -> None:
    line = parse_config(_parts_config(gap_ms=400.0)).lines[0]
    first = _clip(harmonic_voice(120.0, 1.0))
    second = _clip(0.5 * _glide(125.0, 115.0, 0.8))  # quieter: must be level-matched
    joined, rate = assemble([(first, SR), (second, SR)], line.parts)
    assert abs(joined.size / rate - (LEAD_S + 1.0 + 0.4 + 0.8 + TAIL_S)) < 0.06  # 10 ms blocks
    speech_1 = joined[int(LEAD_S * rate) : int((LEAD_S + 1.0) * rate)]
    pause = joined[int((LEAD_S + 1.05) * rate) : int((LEAD_S + 1.35) * rate)]
    speech_2 = joined[int((LEAD_S + 1.4) * rate) : int((LEAD_S + 2.2) * rate)]
    level = 20 * np.log10(np.sqrt(np.mean(speech_2**2)) / np.sqrt(np.mean(speech_1**2)))
    assert abs(level) < 1.0  # the quieter part is matched to the first
    assert 1e-4 < np.std(pause) < 0.02  # room tone through the pause, never digital silence


class _Script:
    """Returns a clip per text and counts calls per text."""

    name = "script"

    def __init__(self, clips: dict[str, bytes]) -> None:
        self.clips, self.calls = clips, {text: 0 for text in clips}

    def synthesize(self, text: str, voice: Mapping[str, Any]) -> bytes:
        self.calls[text] += 1
        return self.clips[text]


def test_a_shared_part_is_recorded_once_for_two_lines(tmp_path: Path) -> None:
    raw = _parts_config()
    twin = dict(raw["lines"][0], id="test.twin")
    twin["parts"] = [{"text": "[calm] Another opening."}, raw["lines"][0]["parts"][1]]
    raw["lines"] = [raw["lines"][0], twin]
    paths = make_paths(tmp_path, raw)
    clips = {
        "[calm] From the final page.": wav_bytes(_clip(harmonic_voice(120.0, 1.0)), SR),
        "[calm] Another opening.": wav_bytes(_clip(harmonic_voice(118.0, 1.2)), SR),
        "[warm] Rise, once more.": wav_bytes(_clip(_glide(125.0, 115.0, 0.8)), SR),
    }
    provider = _Script(clips)
    first, second = parse_config(raw).lines
    assert not has_raw(paths, first)
    data_1 = fetch_raw(paths, first, provider)
    data_2 = fetch_raw(paths, second, provider)
    assert provider.calls["[warm] Rise, once more."] == 1
    assert has_raw(paths, first) and has_raw(paths, second)
    assert read_wav(data_1)[0].size > 0 and read_wav(data_2)[0].size > 0
    assert fetch_raw(paths, first, None) == data_1


def test_phrase_pick_prefers_a_falling_close_near_the_line_pitch() -> None:
    questioning = _clip(_glide(115.0, 175.0, 1.2))
    dull = _clip(_glide(92.0, 90.0, 1.2))
    natural = _clip(_glide(130.0, 112.0, 1.4))
    chosen, phrases = best_phrase([(questioning, SR), (dull, SR), (natural, SR)], ref_f0_hz=120.0)
    assert chosen == 2 and phrases[0].end_slope_hz_s > 0 and phrases[1].f0_vs_ref_hz < -20
