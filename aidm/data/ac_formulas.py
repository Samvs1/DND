"""AC formula schema and the data/bg3/ac_formulas.json loader.

An AC formula is one way to compute a base Armor Class: `base` + the listed ability modifiers
(the DEX part capped by `dex_cap` when set). Features and spells (Unarmored Defense, Mage Armor)
supply formulas by index; worn armor is turned into a formula by `aidm.rules.defense`. The rules
take the best applicable formula, so adding a new one is a data change, not a code change.

Public API:
- `AbilityKey`: the six SRD ability indexes as a Literal (the data layer cannot import
  `aidm.models`; `aidm.models.abilities.Ability(key)` converts).
- `AcFormula(index, name, base, abilities, dex_cap, requires_unarmored, forbids_shield, source)`.
- `load_ac_formulas(path=None) -> Registry[AcFormula]`, `ac_formulas()` (default file, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.data.registry import Registry

type AbilityKey = Literal["str", "dex", "con", "int", "wis", "cha"]

DEFAULT_AC_FORMULAS = (
    Path(__file__).resolve().parents[2] / "data" / "bg3" / "ac_formulas.json"
)


class AcFormula(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    base: int = Field(ge=0)
    abilities: tuple[AbilityKey, ...] = ("dex",)
    dex_cap: int | None = Field(default=None, ge=0)
    requires_unarmored: bool = False
    forbids_shield: bool = False
    source: str = ""


def load_ac_formulas(path: Path | None = None) -> Registry[AcFormula]:
    target = path if path is not None else DEFAULT_AC_FORMULAS
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Registry(AcFormula.model_validate(item) for item in raw)


@functools.cache
def ac_formulas() -> Registry[AcFormula]:
    return load_ac_formulas()
