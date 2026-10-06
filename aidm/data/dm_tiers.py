"""DM tool tier tables: data/bg3/dm_tiers.json (SPEC 6.3: the engine owns every number).

- `severity_dice`: creative-effect damage dice per severity, by party level (rows sorted by
  `max_level`; the first row whose `max_level` >= the party level applies).
- `severity_save_dc` / `severity_max_rounds`: the save DC and longest duration of a creative
  condition per severity.
- `xp_by_level`: XP per PC for a `grant_xp` tier, by party level (same row rule).
- `item_value_cap_gp`: the most a single `grant_item` may be worth (unit value x qty), by region
  tier; `max_item_qty`: the largest stack one grant may give.
- `creative_conditions`: the conditions a creative effect may impose, with the saving throw
  ability that resists them.
- `zone_effect_surfaces`: the surface a zone effect places (difficult terrain, darkness);
  `light_removes`: the surfaces a light effect clears.
- `max_npcs_per_scene` / `max_features_per_scene`: creation caps per scene.
- `deed_points`: attitude points a deed grants, by tier (`aidm.rules.social`).
- `offer_dc_tiers` / `boss_parley_dc_tiers` (M5.4): the DC tier (a `DcTier` value) of the
  escape / surprise / parley checks of a world-pulled encounter, by region tier; parleying
  with a boss uses the second table.
- `quest_gold_gp` (M5.6): gold per living PC for a completed quest, by region tier then reward
  tier; `region_milestone_xp_tier`: the `grant_xp` tier a resolved region pays, by region tier;
  `final_milestone_xp_tier`: the extra tier paid when the last region resolves.
- `spoke_visit_xp_tier` / `spoke_clear_xp_tier` (M9.2): the `grant_xp` tier paid once per spoke
  for its first visit and for clearing it (a won fight or a successful parley there).

Public API: `TierRow`, `DmTiers`, `load_dm_tiers(path=None)`, `dm_tiers()` (default, cached).
The lookups are `aidm.rules.dm_tiers`.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TIER_KEYS = frozenset({"minor", "moderate", "major"})
type AbilityKey = Literal["str", "dex", "con", "int", "wis", "cha"]

DEFAULT_DM_TIERS = Path(__file__).resolve().parents[2] / "data" / "bg3" / "dm_tiers.json"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TierRow(_Strict):
    max_level: int = Field(ge=1, le=20)
    minor: str | int
    moderate: str | int
    major: str | int

    def value(self, tier: str) -> str | int:
        return {"minor": self.minor, "moderate": self.moderate, "major": self.major}[tier]


def _check_rows(rows: tuple[TierRow, ...], name: str) -> None:
    levels = [r.max_level for r in rows]
    if not rows or levels != sorted(levels) or levels[-1] != 20:
        raise ValueError(f"{name}: rows must be sorted by max_level and end at 20")


def _check_reward_tables(tiers: DmTiers) -> None:
    region_tiers = {"1", "2", "3"}
    if set(tiers.quest_gold_gp) != region_tiers:
        raise ValueError("quest_gold_gp needs region tiers 1, 2 and 3")
    if any(set(row) != TIER_KEYS for row in tiers.quest_gold_gp.values()):
        raise ValueError("quest_gold_gp rows need exactly the keys minor, moderate, major")
    named = [
        *tiers.region_milestone_xp_tier.values(),
        tiers.final_milestone_xp_tier,
        tiers.spoke_visit_xp_tier,
        tiers.spoke_clear_xp_tier,
    ]
    if set(tiers.region_milestone_xp_tier) != region_tiers or not set(named) <= TIER_KEYS:
        raise ValueError("milestone XP tiers need region tiers 1-3 and minor/moderate/major values")


class DmTiers(_Strict):
    source: str = ""
    severity_dice: tuple[TierRow, ...]
    severity_save_dc: dict[str, int]
    severity_max_rounds: dict[str, int]
    xp_by_level: tuple[TierRow, ...]
    item_value_cap_gp: dict[str, int]
    max_item_qty: int = Field(ge=1)
    creative_conditions: dict[str, AbilityKey]
    zone_effect_surfaces: dict[str, str]
    light_removes: tuple[str, ...] = ()
    max_npcs_per_scene: int = Field(ge=0)
    max_features_per_scene: int = Field(ge=0)
    deed_points: dict[str, int]
    offer_dc_tiers: dict[str, str] = Field(default_factory=dict[str, str])
    boss_parley_dc_tiers: dict[str, str] = Field(default_factory=dict[str, str])
    quest_gold_gp: dict[str, dict[str, int]]
    region_milestone_xp_tier: dict[str, str]
    final_milestone_xp_tier: str
    spoke_visit_xp_tier: str = "moderate"
    spoke_clear_xp_tier: str = "moderate"

    @model_validator(mode="after")
    def _check(self) -> DmTiers:
        _check_rows(self.severity_dice, "severity_dice")
        _check_rows(self.xp_by_level, "xp_by_level")
        for name in ("severity_save_dc", "severity_max_rounds", "deed_points"):
            if set(getattr(self, name)) != TIER_KEYS:
                raise ValueError(f"{name} needs exactly the keys minor, moderate, major")
        if set(self.item_value_cap_gp) != {"1", "2", "3"}:
            raise ValueError("item_value_cap_gp needs region tiers 1, 2 and 3")
        _check_reward_tables(self)
        return self


def load_dm_tiers(path: Path | None = None) -> DmTiers:
    target = path if path is not None else DEFAULT_DM_TIERS
    return DmTiers.model_validate(json.loads(target.read_text(encoding="utf-8")))


@functools.cache
def dm_tiers() -> DmTiers:
    return load_dm_tiers()
