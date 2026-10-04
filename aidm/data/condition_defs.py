"""Condition definition schema and the data/bg3/conditions.json loader.

Every condition is DATA read by ONE generic interpreter (`aidm.rules.conditions`); adding or
changing a condition is a JSON change, never a per-condition branch in code (SPEC 7.1, 7.4).

Fields of `ConditionDef` (all but index/name/source default to "no effect"):
- `own_attacks`: advantage/disadvantage on the bearer's attack rolls.
- `attacks_against_melee` / `attacks_against_ranged`: on attack rolls against the bearer.
- `auto_crit_melee`: a melee hit against the bearer is a critical hit (attacker within 5 ft).
- `own_checks`: advantage/disadvantage on the bearer's ability checks.
- `auto_fail_saves`, `save_advantage`, `save_disadvantage`: ability keys for saving throws.
- `speed_factor`: multiplies speed (0 = cannot move). `can_act` / `can_react`: actions, reactions.
- `cannot_attack_source`: the bearer cannot attack the creature that applied it (charmed).
- `resist_all_damage`, `damage_immunities`: damage defences while the condition lasts.
- `implies`: other condition keys that apply too (paralyzed implies incapacitated).
- `duration`: the default `DefaultDuration(kind, rounds, tick_on)` for a new instance when the
  applying effect does not say otherwise. `srd_condition` is False for the BG3/SRD-action extras.

Public API: `AdvKey`, `DurationKey`, `BoundaryKey`, `DamageKey`, `DefaultDuration`,
`ConditionDef`, `load_condition_defs(path=None) -> Registry[ConditionDef]` (validates that every
implied key exists and that implications have no cycle), `condition_defs()` (default, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.data.ac_formulas import AbilityKey
from aidm.data.registry import Registry

type AdvKey = Literal["advantage", "disadvantage"]
type DurationKey = Literal["rounds", "until_long_rest", "until_removed"]
type BoundaryKey = Literal["start_of_turn", "end_of_turn"]
type DamageKey = Literal[
    "acid",
    "bludgeoning",
    "cold",
    "fire",
    "force",
    "lightning",
    "necrotic",
    "piercing",
    "poison",
    "psychic",
    "radiant",
    "slashing",
    "thunder",
]

DEFAULT_CONDITIONS = Path(__file__).resolve().parents[2] / "data" / "bg3" / "conditions.json"


class DefaultDuration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: DurationKey = "until_removed"
    rounds: int | None = Field(default=None, ge=1)
    tick_on: BoundaryKey = "end_of_turn"

    @model_validator(mode="after")
    def _check_rounds(self) -> DefaultDuration:
        if (self.kind == "rounds") != (self.rounds is not None):
            raise ValueError("rounds is required for, and only for, kind 'rounds'")
        return self


class ConditionDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source: str = Field(min_length=1)
    srd_condition: bool = True
    own_attacks: AdvKey | None = None
    attacks_against_melee: AdvKey | None = None
    attacks_against_ranged: AdvKey | None = None
    auto_crit_melee: bool = False
    own_checks: AdvKey | None = None
    auto_fail_saves: tuple[AbilityKey, ...] = ()
    save_advantage: tuple[AbilityKey, ...] = ()
    save_disadvantage: tuple[AbilityKey, ...] = ()
    speed_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    can_act: bool = True
    can_react: bool = True
    cannot_attack_source: bool = False
    resist_all_damage: bool = False
    damage_immunities: tuple[DamageKey, ...] = ()
    implies: tuple[str, ...] = ()
    duration: DefaultDuration = DefaultDuration()


def _check_implications(registry: Registry[ConditionDef]) -> None:
    for entry in registry.all():
        seen: set[str] = set()
        stack = list(entry.implies)
        while stack:
            key = stack.pop()
            if key not in registry:
                raise ValueError(f"{entry.index!r} implies unknown condition {key!r}")
            if key == entry.index:
                raise ValueError(f"{entry.index!r} implies itself (cycle)")
            if key not in seen:
                seen.add(key)
                stack.extend(registry.get(key).implies)


def load_condition_defs(path: Path | None = None) -> Registry[ConditionDef]:
    target = path if path is not None else DEFAULT_CONDITIONS
    raw = json.loads(target.read_text(encoding="utf-8"))
    registry = Registry(ConditionDef.model_validate(item) for item in raw)
    _check_implications(registry)
    return registry


@functools.cache
def condition_defs() -> Registry[ConditionDef]:
    return load_condition_defs()
