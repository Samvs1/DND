"""scripts/gen_scribe_voice.py (M13.3): dry run, fake build, --check, --reprocess, key safety."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from aidm.server.voicegen import cli
from aidm.server.voicegen.provider import FakeTts, TtsProvider
from aidm.server.voicegen.runner import VoicePaths
from tests.unit.voicegen.helpers import make_paths, small_config

KEY = "fish-test-key-0123456789abcdef"


class NoProvider:
    name = "none"

    def synthesize(self, text: str, voice: Mapping[str, Any]) -> bytes:
        raise AssertionError("the API must not be called")


def _run(
    args: list[str], paths: VoicePaths, provider: TtsProvider | None = None
) -> tuple[int, str]:
    lines: list[str] = []
    chosen: TtsProvider = provider if provider is not None else NoProvider()
    code = cli.main(
        args,
        root=paths.config.parents[2],
        paths=paths,
        provider_factory=lambda: chosen,
        out=lines.append,
    )
    return code, "\n".join(lines)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[VoicePaths, FakeTts, str]:
    paths = make_paths(tmp_path_factory.mktemp("voice"))
    fake = FakeTts(max_seconds=1.5)
    code, text = _run(["--yes"], paths, fake)
    assert code == 0, text
    return paths, fake, text


def test_dry_run_plans_and_writes_nothing(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    code, text = _run([], paths)
    assert code == 0
    assert "API calls: 2" in text and "test.long" in text
    assert not paths.raw_dir.exists() and not paths.out_dir.exists()
    assert text.isascii()


def test_yes_builds_files_index_and_report(built: tuple[VoicePaths, FakeTts, str]) -> None:
    paths, fake, text = built
    assert len(fake.calls) == 2
    assert text.isascii()
    index = json.loads((paths.out_dir / "lines.json").read_text(encoding="utf-8"))
    assert [e["id"] for e in index["lines"]] == ["test.long", "test.short"]
    for entry in index["lines"]:
        mp3 = paths.out_dir / entry["file"]
        assert mp3.read_bytes()[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3") or mp3.stat().st_size > 0
        assert abs(entry["lufs"] + 16.0) < 0.5 and entry["true_peak_db"] <= -1.0
        report = json.loads((paths.report_dir / f"{entry['id']}.json").read_text("utf-8"))
        assert abs(report["f0_delta_pct"]) < 1.0
        with Image.open(paths.report_dir / f"{entry['id']}.png") as png:
            assert png.width == 1200 and png.height > 400
    assert "| test.short |" in (paths.report_dir / "report.md").read_text(encoding="utf-8")
    assert len(list(paths.raw_dir.glob("*.wav"))) == 2


def test_check_passes_then_fails_on_text_edit(built: tuple[VoicePaths, FakeTts, str]) -> None:
    paths, _, _ = built
    assert _run(["--check"], paths)[0] == 0
    original = paths.config.read_text(encoding="utf-8")
    try:
        paths.config.write_text(json.dumps(small_config(text="New words.")), encoding="utf-8")
        code, text = _run(["--check"], paths)
        assert code == 1 and "test.long: text changed" in text
    finally:
        paths.config.write_text(original, encoding="utf-8")


def test_check_fails_on_tampered_or_missing_file(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    assert _run(["--check"], paths)[0] == 1  # nothing built yet
    assert _run(["--yes", "--only", "test.short"], paths, FakeTts(max_seconds=1.2))[0] == 0
    code, text = _run(["--check"], paths)
    assert code == 1 and "test.long: not in lines.json" in text
    assert "test.short" not in text
    (paths.out_dir / "test.short.mp3").write_bytes(b"tampered")
    code, text = _run(["--check"], paths)
    assert code == 1 and "test.short: test.short.mp3 differs" in text


def test_reprocess_uses_cache_only(built: tuple[VoicePaths, FakeTts, str]) -> None:
    paths, fake, _ = built
    before = len(fake.calls)
    code, text = _run(["--reprocess", "--only", "test.short"], paths)  # NoProvider explodes
    assert code == 0, text
    assert len(fake.calls) == before
    assert _run(["--check"], paths)[0] == 0


def test_reprocess_missing_raw_names_the_line(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    code, text = _run(["--reprocess"], paths)
    assert code == 2 and "test.long: no cached raw WAV" in text
    assert not paths.out_dir.exists()


def test_bad_arguments(tmp_path: Path) -> None:
    paths = make_paths(tmp_path)
    assert _run(["--only", "nope"], paths)[0] == 1
    assert _run(["--yes", "--reprocess"], paths)[0] == 1


def test_key_never_reaches_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = make_paths(tmp_path)
    monkeypatch.setenv("FISH_API_KEY", KEY)
    monkeypatch.setenv("VOICE_PROVIDER", "fake")
    lines: list[str] = []
    code = cli.main(["--yes", "--only", "test.short"], root=tmp_path, paths=paths, out=lines.append)
    assert code == 0
    assert KEY not in "\n".join(lines)
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert KEY.encode() not in path.read_bytes(), path.name


def test_missing_key_is_exit_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = make_paths(tmp_path)
    monkeypatch.setenv("FISH_API_KEY", "")
    monkeypatch.setenv("VOICE_PROVIDER", "fish")
    lines: list[str] = []
    code = cli.main(["--yes"], root=tmp_path, paths=paths, out=lines.append)
    assert code == 3 and "FISH_API_KEY is not set" in "\n".join(lines)
