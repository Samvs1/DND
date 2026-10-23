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
- M29.6 tuning: `spoke_budget_scale[region tier]` multiplies a spoke's rating cap (default 1.0:
  the whole tier up to the next threshold); `spoke_stand_ins` (when no theme monster fits a spoke's budget, encounter-ready
  monsters sharing a terrain with the themes stand in, at the highest XP that fits, instead of
  the cheapest theme monster over budget); `boss_company_max_per_pc` caps the boss's company at
  that multiple of the party size (None: only the budget and `max_monsters`); a boss whose own
  adjusted XP is over the boss cap (a small party) spawns with its hit points scaled by
  cap / adjusted XP, never below `boss_hp_scale_floor` (None: never scaled).
- M29.6b area danger (`aidm.rules.encounter_danger`): `area_damage_rating[difficulty]` is the
  share of the heroes' average hit point maximum one area blast (a breath weapon) must reach to
  rate the fight at least that difficulty (empty: off); `area_reference_hp[region tier]` is a
  hero's average maximum at the tier's planned level, which the plan check uses for masters;
  `boss_budget_scale[region tier]` multiplies the boss cap's XP for the master's company and
  hit point scale (default 1.0), as `spoke_budget_scale` does for spokes.
- M29.7d round damage (`aidm.rules.encounter_threat`): `round_damage_rating[difficulty]` is the
  share of the heroes' average hit point maximum one foe's expected damage per round must reach
  to rate the fight at least that difficulty (empty: off); `cover_rating_step[cover]` adds steps
  when a foe with a ranged attack fights from a zone with that cover ("half", "three_quarters").

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
    spoke_stand_ins: bool = False
    spoke_budget_scale: dict[int, float] = Field(default_factory=dict[int, float])
    boss_company_max_per_pc: int | None = Field(default=None, ge=0)
    boss_hp_scale_floor: float | None = Field(default=None, gt=0, le=1.0)
    area_damage_rating: dict[DifficultyKey, float] = Field(
        default_factory=dict[DifficultyKey, float]
    )
    area_reference_hp: dict[int, float] = Field(default_factory=dict[int, float])
    round_damage_rating: dict[DifficultyKey, float] = Field(
        default_factory=dict[DifficultyKey, float]
    )
    cover_rating_step: dict[str, int] = Field(default_factory=dict[str, int])
    boss_budget_scale: dict[int, float] = Field(default_factory=dict[int, float])

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
