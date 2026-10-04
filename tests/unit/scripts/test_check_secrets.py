import subprocess
from pathlib import Path

import pytest

from .helpers import load_script, write

sec = load_script("check_secrets")

SECRET = "sk-abcdef123456"


def test_parse_env_ignores_comments_blanks_and_short_values() -> None:
    text = "# comment\n\nKEY_A=" + SECRET + '\nSHORT=abc\nQUOTED="quotedvalue99"\nNOEQ\n'
    assert sec.parse_env_values(text) == [SECRET, "quotedvalue99"]


def test_scan_finds_secret_and_returns_path_only(tmp_path: Path) -> None:
    write(tmp_path, "a.txt", "token = " + SECRET + "\n")
    write(tmp_path, "b.txt", "nothing here\n")
    assert sec.scan_files(tmp_path, [SECRET], ["a.txt", "b.txt"]) == ["a.txt"]


def test_scan_clean_files_pass(tmp_path: Path) -> None:
    write(tmp_path, "b.txt", "nothing here\n")
    assert sec.scan_files(tmp_path, [SECRET], ["b.txt", "missing.txt"]) == []


def test_scan_ignores_short_values(tmp_path: Path) -> None:
    write(tmp_path, "a.txt", "abc\n")
    assert sec.scan_files(tmp_path, ["abc"], ["a.txt"]) == []


def test_main_without_env_skips(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert sec.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "no .env, skipped"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_main_hit_prints_path_never_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _git(tmp_path, "init")
    write(tmp_path, ".env", "MY_SECRET_KEY=" + SECRET + "\n")
    write(tmp_path, "leak.txt", "oops " + SECRET + "\n")
    _git(tmp_path, "add", "leak.txt")
    assert sec.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "leak.txt" in out
    assert SECRET not in out
    assert "MY_SECRET_KEY" not in out


def test_main_clean_repo_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _git(tmp_path, "init")
    write(tmp_path, ".env", "MY_SECRET_KEY=" + SECRET + "\n")
    write(tmp_path, "ok.txt", "fine\n")
    _git(tmp_path, "add", "ok.txt")
    assert sec.main([str(tmp_path)]) == 0
    assert SECRET not in capsys.readouterr().out
