"""The Scribe's lines: the texts of data/voice/scribe.json (M13.2, docs/next/GOAL_SCRIBE.md).

That file is the ONE source of what he says: the game reads each line's `id`, `group`, `text`
and `profile` from it; the voice settings and the sound chain in the same file belong to the
voice build (M13.3) and are ignored here.

- `ScribeGroup`: the moments he speaks (welcome_first, welcome_return, victory_campaign, revive,
  refuse_combat, refuse_funds, none_fallen, not_yet). He does not speak after an ordinary fight
  (owner feedback, M13.4).
- `ScribeLine(id, group, text, profile)`: `text` is the spoken text and may carry Fish S2 cues in
  square brackets (`[break]`, `[long-break]`, `[calm, warm]`); `ScribeLine.display` is the same
  text with every cue removed, which is what players read. `voiced` False marks a text-only line
  (the refusals): he speaks aloud only for the welcome, welcome back, campaign victory and revive. `ScribeLines.group(name)` -> the lines
  of one group in file order. Every group has at least one line and ids are unique.
- `audio_url(line_id, static_dir=None)`: "/static/audio/voice/scribe/<line_id>.mp3" when that
  file exists under the web static folder, else "" (the voice build creates the files).

Public API: `ScribeGroup`, `ScribeLine`, `ScribeLines`, `load_scribe_lines(path=None)`,
`scribe_lines()` (cached), `audio_url`, `DEFAULT_LINES`, `DEFAULT_STATIC`.
"""

from __future__ import annotations

import functools
import json
import re
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_LINES = Path(__file__).resolve().parents[2] / "data" / "voice" / "scribe.json"
DEFAULT_STATIC = Path(__file__).resolve().parents[1] / "web" / "static"
VOICE_PARTS = ("audio", "voice", "scribe")
_CUE = re.compile(r"\s*\[[^\]]*\]\s*")


class ScribeGroup(StrEnum):
    WELCOME_FIRST = "welcome_first"
    WELCOME_RETURN = "welcome_return"
    VICTORY_CAMPAIGN = "victory_campaign"
    REVIVE = "revive"
    REFUSE_COMBAT = "refuse_combat"
    REFUSE_FUNDS = "refuse_funds"
    NONE_FALLEN = "none_fallen"
    NOT_YET = "not_yet"


class ScribeLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str = Field(min_length=1, pattern=r"^[a-z0-9_.]+$")
    group: ScribeGroup
    text: str = Field(min_length=1)
    profile: str = "long"
    voiced: bool = True  # False: shown as text only, no audio is built for it

    @property
    def display(self) -> str:
        """The text without the [bracket] speech cues, as players read it."""
        return " ".join(_CUE.sub(" ", self.text).split())


class ScribeLines(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    lines: tuple[ScribeLine, ...]

    @model_validator(mode="after")
    def _complete(self) -> ScribeLines:
        ids = [line.id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate Scribe line id")
        missing = {g for g in ScribeGroup} - {line.group for line in self.lines}
        if missing:
            raise ValueError(f"Scribe groups without a line: {sorted(missing)}")
        return self

    def group(self, name: ScribeGroup) -> tuple[ScribeLine, ...]:
        return tuple(line for line in self.lines if line.group is name)


def load_scribe_lines(path: Path | None = None) -> ScribeLines:
    target = path if path is not None else DEFAULT_LINES
    return ScribeLines.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def scribe_lines() -> ScribeLines:
    return load_scribe_lines()


def audio_url(line_id: str, static_dir: Path | None = None) -> str:
    root = static_dir if static_dir is not None else DEFAULT_STATIC
    if not root.joinpath(*VOICE_PARTS, f"{line_id}.mp3").is_file():
        return ""
    return "/static/" + "/".join((*VOICE_PARTS, f"{line_id}.mp3"))
