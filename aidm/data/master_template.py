"""The master template (M31.1d): data/bg3/master_template.json, loaded once.

A region's master fights a full party (`party_min` heroes or more) with a general boost read by
the one interpreter (`aidm.rules.master_boost`), never per-monster code:
- `hit_dice_share`: its hit points move from the stat block's average towards the maximum of its
  hit dice (0: the SRD average, 1: every die at its highest; "6d8+18" -> 45 .. 66);
- `legendary_points`: a master's turn, the points of a lite legendary action pool refilled at
  the start of its own turn and spent (one per use) on one of its own single attacks at the end
  of another creature's turn (`aidm.rules.monster_legendary`); 0: none; `legendary_recharge`:
  a spent pool refills at the start of the master's turn on a d6 of at least this (1: always,
  5: the SRD "Recharge 5-6");
- `trait`: a features.json trait stamped on the master (data hooks, for example advantage on
  saves against being stunned or held); None: none;
- `full_party_hp_share` (M31.1g, owner 2026-10-24 "Tune HP to the cap"): region tier -> the
  share of its hit points (after `hit_dice_share`) a full party's master spawns with; a tier
  not listed: 1.0. Never below the old M29.6 small-party scale (what round 4 met), see
  `aidm.rules.master_boost`.
Every master, whatever the party size, is never weaker than the region's own spoke fights:
below the strongest spoke group's adjusted XP its hit points rise by that ratio, at most
`floor_hp_scale_max`. Solo and duo parties keep the M29.6 small-party hit point scale instead
of the template (owner rule, docs/DECISIONS.md).

Public API: `MasterTemplate`, `load_master_template(path=None)`, `master_template()` (cached).
`MasterTemplate()` is the template switched off (old tests and tools that pass none).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MASTER_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "data" / "bg3" / "master_template.json"
)


class MasterTemplate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    note: str = ""
    party_min: int = Field(default=3, ge=1, le=8)
    hit_dice_share: float = Field(default=0.0, ge=0.0, le=1.0)
    legendary_points: int = Field(default=0, ge=0, le=3)
    legendary_recharge: int = Field(default=1, ge=1, le=6)
    trait: str | None = None
    floor_hp_scale_max: float = Field(default=1.0, ge=1.0, le=4.0)
    full_party_hp_share: dict[int, Annotated[float, Field(gt=0.0, le=1.0)]] = Field(
        default_factory=dict[int, float]
    )


def load_master_template(path: Path | None = None) -> MasterTemplate:
    target = path if path is not None else DEFAULT_MASTER_TEMPLATE
    return MasterTemplate.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def master_template() -> MasterTemplate:
    return load_master_template()
