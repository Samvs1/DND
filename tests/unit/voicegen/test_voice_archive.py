"""The lossless archive of approved raw takes (owner: a paper trail in git)."""

import json
import shutil
from pathlib import Path

import numpy as np

from aidm.server.voicegen.archive import archive_used, from_flac, missing, orphans, to_flac
from aidm.server.voicegen.provider import FakeTts, read_wav, wav_bytes
from aidm.server.voicegen.runner import VoicePaths
from tests.unit.voicegen.helpers import SR, harmonic_voice, make_paths
from tests.unit.voicegen.test_gen_scribe_voice_cli import _run


def test_flac_round_trip_keeps_every_sample() -> None:
    wav = wav_bytes(harmonic_voice(120.0, 0.5), SR)
    back = from_flac(to_flac(wav))
    a, rate_a = read_wav(wav)
    b, rate_b = read_wav(back)
    assert rate_a == rate_b and np.array_equal(a, b)
    assert len(to_flac(wav)) < len(wav)


def test_archive_missing_and_orphans(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "line.1__abc.wav"
    raw.parent.mkdir()
    raw.write_bytes(wav_bytes(harmonic_voice(120.0, 0.3), SR))
    archive = tmp_path / "takes"
    assert missing([raw], archive) == ["line.1__abc.wav"]
    assert archive_used([raw], archive) == ["line.1__abc.flac"]
    assert archive_used([raw], archive) == []  # append only, nothing rewritten
    assert missing([raw], archive) == []
    assert orphans([], archive) == ["line.1__abc.flac"]


def _build(tmp_path: Path) -> VoicePaths:
    paths = make_paths(tmp_path)
    code, text = _run(["--yes"], paths, FakeTts(max_seconds=1.0))
    assert code == 0 and "archived" in text, text
    return paths


def test_a_fresh_clone_rebuilds_from_the_archive_without_the_api(tmp_path: Path) -> None:
    paths = _build(tmp_path)
    index = json.loads((paths.out_dir / "lines.json").read_text(encoding="utf-8"))
    assert len(list(paths.archive_dir.glob("*.flac"))) == 2
    shutil.rmtree(paths.raw_dir)  # the gitignored cache is gone, as in a fresh clone
    code, text = _run(["--reprocess"], paths)  # NoProvider: any API call fails the test
    assert code == 0, text
    again = json.loads((paths.out_dir / "lines.json").read_text(encoding="utf-8"))
    for before, after in zip(index["lines"], again["lines"], strict=True):
        assert before["id"] == after["id"] and abs(before["lufs"] - after["lufs"]) < 0.01


def test_check_fails_when_a_used_take_is_not_archived(tmp_path: Path) -> None:
    paths = _build(tmp_path)
    assert _run(["--check"], paths)[0] == 0
    next(paths.archive_dir.glob("*.flac")).unlink()
    code, text = _run(["--check"], paths)
    assert code == 1 and "not archived" in text
