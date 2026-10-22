"""Zone template schema and the data/bg3/zone_templates.json loader.

Encounter maps are generated from terrain tags (SPEC 7.3) by ONE generic generator
(`aidm.rules.zone_gen.generate_zone_map`); every terrain and zone is data here, never code.
The wording is original (no BG3 text).

- `ZoneTemplate(key, names, tags, distance_label, cover, high_ground, difficult)`: one zone the
  generator may place; `key` becomes the zone id, one of `names` its display name.
- `TerrainTemplate(index, name, hop_feet, zones)`: a terrain tag ("forest", "cave"); `hop_feet`
  is the movement cost of every edge on a map of this terrain (open ground 30, tight 15).
  A terrain offers at least `MIN_TEMPLATE_ZONES` zones with unique keys.
- `FALLBACK_TERRAIN` ("wilds"): used when none of the requested tags is known.

Public API: `load_zone_templates(path=None) -> Registry[TerrainTemplate]` (requires the fallback
terrain), `zone_templates()` (default file, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.data.registry import Registry

type CoverKey = Literal["none", "half", "three_quarters"]

DEFAULT_ZONE_TEMPLATES = (
    Path(__file__).resolve().parents[2] / "data" / "bg3" / "zone_templates.json"
)
FALLBACK_TERRAIN = "wilds"
MIN_TEMPLATE_ZONES = 6


class ZoneTemplate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    names: tuple[str, ...] = Field(min_length=1)
    tags: tuple[str, ...] = ()
    distance_label: str = ""
    cover: CoverKey = "none"
    high_ground: bool = False
    difficult: bool = False


class TerrainTemplate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    hop_feet: int = Field(default=30, ge=5)
    dark: bool = False  # M27.1: every zone of this terrain is dark unless lit
    zones: tuple[ZoneTemplate, ...]

    @model_validator(mode="after")
    def _check_zones(self) -> TerrainTemplate:
        keys = [z.key for z in self.zones]
        if len(keys) < MIN_TEMPLATE_ZONES:
            raise ValueError(f"terrain {self.index!r} needs >= {MIN_TEMPLATE_ZONES} zones")
        if len(set(keys)) != len(keys):
            raise ValueError(f"terrain {self.index!r} has duplicate zone keys")
        return self


def load_zone_templates(path: Path | None = None) -> Registry[TerrainTemplate]:
    target = path if path is not None else DEFAULT_ZONE_TEMPLATES
    raw = json.loads(target.read_text(encoding="utf-8"))
    registry = Registry(TerrainTemplate.model_validate(item) for item in raw)
    if FALLBACK_TERRAIN not in registry:
        raise ValueError(f"zone templates need the fallback terrain {FALLBACK_TERRAIN!r}")
    return registry


@functools.cache
def zone_templates() -> Registry[TerrainTemplate]:
    return load_zone_templates()
