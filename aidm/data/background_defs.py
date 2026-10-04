"""Background schema and the data/bg3/backgrounds.json loader (original wording, no BG3 text).

A background grants two skill proficiencies, tool proficiencies (SRD proficiency indexes),
starting gear (SRD equipment indexes with quantities) and carries one flavour line for the DM.

Public API: `BackgroundDef`, `load_background_defs(path=None) -> Registry[BackgroundDef]`,
`background_defs()` (default, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.data.char_common import ItemQty
from aidm.data.registry import Registry

DEFAULT_BACKGROUNDS = Path(__file__).resolve().parents[2] / "data" / "bg3" / "backgrounds.json"


class BackgroundDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    skills: tuple[str, str]
    tools: tuple[str, ...] = ()
    gear: tuple[ItemQty, ...] = Field(min_length=1)
    flavour: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _check_skills(self) -> BackgroundDef:
        if self.skills[0] == self.skills[1]:
            raise ValueError("a background grants two different skills")
        return self


def load_background_defs(path: Path | None = None) -> Registry[BackgroundDef]:
    target = path if path is not None else DEFAULT_BACKGROUNDS
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Registry(BackgroundDef.model_validate(item) for item in raw)


@functools.cache
def background_defs() -> Registry[BackgroundDef]:
    return load_background_defs()
