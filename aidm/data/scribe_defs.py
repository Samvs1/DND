"""The Scribe's price table: data/bg3/scribe.json (M13.1, house rule, docs/next/GOAL_SCRIBE.md).

- `base_gp`, `per_level_gp`: a revive costs `base_gp + per_level_gp x level` of the fallen hero.
- `restore`: the HP a rewritten hero returns with: "half" (max HP / 2, rounded up), "one" or
  "full".
- `payment`: who pays; "payer" = the requesting player's own hero (the only mode so far).
- `keep_conditions`: condition names a revive does not clear (exhaustion).

Public API: `RestoreMode`, `ScribeTable`, `load_scribe_table(path=None)`, `scribe_table()`
(cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_SCRIBE = Path(__file__).resolve().parents[2] / "data" / "bg3" / "scribe.json"

type RestoreMode = Literal["half", "one", "full"]


class ScribeTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = ""
    base_gp: int = Field(default=0, ge=0)
    per_level_gp: int = Field(ge=0)
    restore: RestoreMode = "half"
    payment: Literal["payer"] = "payer"
    keep_conditions: tuple[str, ...] = ()


def load_scribe_table(path: Path | None = None) -> ScribeTable:
    target = path if path is not None else DEFAULT_SCRIBE
    return ScribeTable.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def scribe_table() -> ScribeTable:
    return load_scribe_table()
