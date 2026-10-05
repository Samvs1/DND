"""Per-tone TTS prosody: data/bg3/tts_tones.json (SPEC 4 Fish Audio, 11).

Public API: `ToneParams`, `TtsTones` (`params(tone)`), `load_tts_tones(path=None)`, `tts_tones()`
(default, cached). An unknown or empty tone falls back to the `default` row.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_TTS_TONES = Path(__file__).resolve().parents[2] / "data" / "bg3" / "tts_tones.json"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToneParams(_Strict):
    speed: float = Field(ge=0.5, le=2.0)
    volume: float = Field(ge=-20.0, le=20.0)
    temperature: float = Field(ge=0.0, le=1.0)


class TtsTones(_Strict):
    source: str = ""
    default: ToneParams
    tones: dict[str, ToneParams]

    def params(self, tone: str | None) -> ToneParams:
        return self.tones.get((tone or "").strip().lower(), self.default)


def load_tts_tones(path: Path | None = None) -> TtsTones:
    raw = json.loads((path or DEFAULT_TTS_TONES).read_text(encoding="utf-8"))
    return TtsTones.model_validate(raw)


@functools.cache
def tts_tones() -> TtsTones:
    return load_tts_tones()
