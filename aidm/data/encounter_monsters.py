"""Encounter-ready monster list: data/bg3/encounter_monsters.json (M3.9).

The curated subset of SRD monsters (CR <= 8) whose whole stat block the monster action catalog
(`aidm.rules.monster_catalog`) can run. The JSON is hand-curated (`scripts/build_monster_catalog.py`
prints the candidates); this module is a data-layer lookup only, with no game logic.

`EncounterMonster` fields:
- `index`: the SRD monster index; `cr`: its challenge rating.
- `tier`: the region tier (1: CR 0-1, 2: CR 2-4, 3: CR 5-8).
- `tags`: terrain tags (the terrains of data/bg3/zone_templates.json) the monster fits.
- `role`: brute / skirmisher / artillery / caster / controller / leader / minion.
- `cosmetic_unsupported`: catalog `unsupported` entries accepted for this monster (utility spells,
  a skipped trait); a monster with any other unsupported entry is not encounter-ready.

Public API: `load_encounter_monsters(path=None) -> Registry[EncounterMonster]`,
`encounter_monsters()` (default file, cached),
`encounter_candidates(tier, tags, *, include_lower=False) -> tuple[EncounterMonster, ...]`.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.data.registry import Registry

type MonsterRole = Literal[
    "brute", "skirmisher", "artillery", "caster", "controller", "leader", "minion"
]

DEFAULT_ENCOUNTER_MONSTERS = (
    Path(__file__).resolve().parents[2] / "data" / "bg3" / "encounter_monsters.json"
)
FALLBACK_TAG = "wilds"
MAX_CR = 8


def tier_for_cr(cr: float) -> int:
    return 1 if cr <= 1 else 2 if cr <= 4 else 3


class EncounterMonster(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: str = Field(min_length=1)
    cr: float = Field(ge=0, le=MAX_CR)
    tier: int = Field(ge=1, le=3)
    tags: tuple[str, ...] = Field(min_length=1)
    role: MonsterRole
    cosmetic_unsupported: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check_tier(self) -> EncounterMonster:
        if self.tier != tier_for_cr(self.cr):
            raise ValueError(f"{self.index!r}: tier {self.tier} does not match CR {self.cr}")
        return self


def load_encounter_monsters(path: Path | None = None) -> Registry[EncounterMonster]:
    target = path if path is not None else DEFAULT_ENCOUNTER_MONSTERS
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Registry(EncounterMonster.model_validate(item) for item in raw)


@functools.cache
def encounter_monsters() -> Registry[EncounterMonster]:
    return load_encounter_monsters()


def encounter_candidates(
    tier: int, tags: Iterable[str] = (), *, include_lower: bool = False
) -> tuple[EncounterMonster, ...]:
    """Monsters of region `tier` (and lower tiers with `include_lower`) sharing a terrain tag.

    No tags matches every terrain. When no monster fits the tags, the "wilds" ones are returned
    (the zone generator's fallback terrain).
    """
    wanted = set(tags)
    in_tier = encounter_monsters().filter(
        lambda m: m.tier == tier or (include_lower and m.tier < tier)
    )
    if not wanted:
        return in_tier
    fits = tuple(m for m in in_tier if wanted & set(m.tags))
    return fits or tuple(m for m in in_tier if FALLBACK_TAG in m.tags)
