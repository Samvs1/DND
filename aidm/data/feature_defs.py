"""Feature definitions and the data/bg3/features.json loader (SPEC 7.4: one entry per feature).

Every class, subclass and race feature id the shipped data references (class levels, subclass
features, class choice options, race and subrace traits) has exactly one `FeatureDef` here, and so
do the options a feature lets the player pick (draconic ancestry colours). The hooks are
interpreted by `aidm.rules.features` / `aidm.rules.feature_build`.

Fields of `FeatureDef`:
- `index` (SRD feature/trait index or a `bg3-` id), `name`, `summary` (original short wording for
  the sheet, at most 200 characters).
- `hooks`: typed effects (`aidm.data.feature_hooks.FeatureHook`); empty for a feature that is
  narrative or is applied by other data (spellcasting by the slot model, race proficiencies by
  races.json, subclass choice by level-up).
- `pick`: the player picks `choose` of `options` (other feature indexes) when gaining it; picked
  ids join the character's features (class) or traits (race). Expertise picks are skills and use
  the `expertise` hook instead.

Public API: `FeatureDef`, `load_feature_defs(path=None) -> Registry[FeatureDef]` (checks that
every pick option exists), `feature_defs()` (default, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from aidm.data.char_common import PickList
from aidm.data.feature_hooks import FeatureHook
from aidm.data.registry import Registry

DEFAULT_FEATURES = Path(__file__).resolve().parents[2] / "data" / "bg3" / "features.json"
MAX_SUMMARY_CHARS = 200


class FeatureDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=MAX_SUMMARY_CHARS)
    hooks: tuple[FeatureHook, ...] = ()
    pick: PickList | None = None


def load_feature_defs(path: Path | None = None) -> Registry[FeatureDef]:
    target = path if path is not None else DEFAULT_FEATURES
    raw = json.loads(target.read_text(encoding="utf-8"))
    registry = Registry(FeatureDef.model_validate(item) for item in raw)
    for entry in registry.all():
        missing = [o for o in (entry.pick.options if entry.pick else ()) if o not in registry]
        if missing:
            raise ValueError(f"{entry.index!r} offers unknown features {missing}")
    return registry


@functools.cache
def feature_defs() -> Registry[FeatureDef]:
    return load_feature_defs()
