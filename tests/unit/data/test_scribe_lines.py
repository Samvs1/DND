"""The Scribe's line loader (M13.2): data/voice/scribe.json is the one source of his texts."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm.data.scribe_lines import (
    DEFAULT_LINES,
    ScribeGroup,
    audio_url,
    load_scribe_lines,
    scribe_lines,
)

# docs/next/GOAL_SCRIBE.md "What he does" 1-3 (decisions D: variant counts per moment)
EXPECTED_COUNTS = {
    ScribeGroup.WELCOME_FIRST: 1,
    ScribeGroup.WELCOME_RETURN: 1,
    ScribeGroup.VICTORY_FIGHT: 5,
    ScribeGroup.VICTORY_CAMPAIGN: 3,
    ScribeGroup.REVIVE: 3,
    ScribeGroup.REFUSE_COMBAT: 2,
    ScribeGroup.REFUSE_FUNDS: 2,
    ScribeGroup.NONE_FALLEN: 1,
    ScribeGroup.NOT_YET: 1,
}


def test_every_group_has_its_lines_in_file_order() -> None:
    lines = scribe_lines()
    assert {g: len(lines.group(g)) for g in ScribeGroup} == EXPECTED_COUNTS
    assert [line.id for line in lines.group(ScribeGroup.REVIVE)] == [
        "revive.1",
        "revive.2",
        "revive.3",
    ]
    assert all(line.text.strip() and line.text.isascii() for line in lines.lines)


def test_texts_come_from_the_voice_config() -> None:
    raw = json.loads(DEFAULT_LINES.read_text(encoding="utf-8"))
    by_id = {line["id"]: line["text"] for line in raw["lines"]}
    assert {line.id: line.text for line in scribe_lines().lines} == by_id


def _write(tmp_path: Path, lines: list[dict[str, str]]) -> Path:
    path = tmp_path / "scribe.json"
    path.write_text(json.dumps({"voice": {}, "chain": {}, "lines": lines}), encoding="utf-8")
    return path


def _all_groups() -> list[dict[str, str]]:
    return [{"id": f"{g.value}.1", "group": g.value, "text": "Ah."} for g in ScribeGroup]


def test_a_missing_group_or_a_duplicate_id_is_refused(tmp_path: Path) -> None:
    assert len(load_scribe_lines(_write(tmp_path, _all_groups())).lines) == len(ScribeGroup)
    with pytest.raises(ValidationError, match="without a line"):
        load_scribe_lines(_write(tmp_path, _all_groups()[1:]))
    with pytest.raises(ValidationError, match="duplicate"):
        load_scribe_lines(_write(tmp_path, [*_all_groups(), _all_groups()[0]]))
    unknown = [*_all_groups(), {"id": "x.1", "group": "gossip", "text": "Hm."}]
    with pytest.raises(ValidationError):
        load_scribe_lines(_write(tmp_path, unknown))


def test_audio_url_only_when_the_file_exists(tmp_path: Path) -> None:
    assert audio_url("revive.1", tmp_path) == ""
    folder = tmp_path / "audio" / "voice" / "scribe"
    folder.mkdir(parents=True)
    (folder / "revive.1.mp3").write_bytes(b"ID3")
    assert audio_url("revive.1", tmp_path) == "/static/audio/voice/scribe/revive.1.mp3"
    assert audio_url("revive.2", tmp_path) == ""
