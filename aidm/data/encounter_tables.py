"""Encounter budget tables: data/bg3/encounter_budget.json (one file, loaded once).

- `thresholds[level][difficulty]`: XP threshold per character level (levels 1-12).
- `multiplier_steps`: the group multiplier by monster count (highest `min_monsters` <= count).
- Party size adjustment: a party of `small_party_max` or fewer uses the next step up the
  ladder (past the last step: `small_party_top_multiplier`); a party of `large_party_min` or
  more the next step down (one monster: `large_party_multiplier`).
- `max_monsters`: the most monsters `pick_monsters` ever places.
- World-pulled encounters (M9.2, RULES_DECISIONS): `spoke_rating_cap[region tier]` is the
  highest difficulty rating a spoke's monster list may reach (tier 1: easy), `boss_rating_cap`
  the boss fight's (hard); `spoke_max_monsters_per_pc[region tier]` caps a spoke's monster count
  at that multiple of the party size (action economy).

Public API: `EncounterTables`, `MultiplierStep`, `load_encounter_tables(path=None)`,
`encounter_tables()` (default file, cached). The arithmetic is `aidm.rules.encounter_budget`.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

type DifficultyKey = Literal["easy", "medium", "hard", "deadly"]

DEFAULT_ENCOUNTER_TABLES = (
    Path(__file__).resolve().parents[2] / "data" / "bg3" / "encounter_budget.json"
)


class MultiplierStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min_monsters: int = Field(ge=1)
    multiplier: float = Field(gt=0)


class EncounterTables(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(min_length=1)
    thresholds: dict[int, dict[DifficultyKey, int]]
    multiplier_steps: tuple[MultiplierStep, ...] = Field(min_length=1)
    small_party_top_multiplier: float = Field(gt=0)
    large_party_multiplier: float = Field(gt=0)
    small_party_max: int = Field(ge=0)
    large_party_min: int = Field(ge=1)
    max_monsters: int = Field(ge=1)
    spoke_rating_cap: dict[int, DifficultyKey] = Field(
        default_factory=lambda: dict[int, DifficultyKey]({1: "easy", 2: "medium", 3: "medium"})
    )
    spoke_max_monsters_per_pc: dict[int, int] = Field(default_factory=dict[int, int])
    boss_rating_cap: DifficultyKey = "hard"

    @model_validator(mode="after")
    def _check(self) -> EncounterTables:
        counts = [s.min_monsters for s in self.multiplier_steps]
        if counts[0] != 1 or counts != sorted(set(counts)):
            raise ValueError("multiplier steps must start at 1 and strictly increase")
        for level, row in self.thresholds.items():
            if len(row) != 4:
                raise ValueError(f"level {level} needs all four difficulty thresholds")
        return self


def load_encounter_tables(path: Path | None = None) -> EncounterTables:
    target = path if path is not None else DEFAULT_ENCOUNTER_TABLES
    return EncounterTables.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def encounter_tables() -> EncounterTables:
    return load_encounter_tables()
