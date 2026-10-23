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
- `ac_bonus`: added to the bearer's AC (AC buffs such as Shield of Faith); `ac_floor`: the
  bearer's AC is at least this (Barkskin). `attack_dice` / `save_dice` / `check_dice`: a dice
  expression added to the bearer's attack rolls / saving throws / ability checks (Bless,
  Resistance, Guidance); a leading "-" subtracts it instead (Bane: "-1d4").
  `consumed_by_attack`: the instance ends when the bearer makes an attack roll (hidden, helped).
  `ends_on_damage`: the instance ends when the bearer takes damage (magical sleep).
  `ends_on_source_side_harm` (M29.7d): the instance ends when the creature that applied it, or
  anyone on its side, damages the bearer (SRD 5.1 Animal Friendship, Charm Person: "if you or
  your companions harm it"); a hostile befriended so by the party no longer keeps a fight going.
- `unseen` / `sightless` (M29.7d): others cannot see the bearer (invisible, hidden) / the
  bearer cannot see (blinded); read by "Ranged Attacks in Close Combat" (`rules.hit_chance`).
- `speed_bonus`: feet added to the bearer's speed while it can move (Longstrider).
- `damage_resistances`: damage types the bearer resists while the condition lasts.
- `source_rider_dice` / `source_rider_type`: extra damage when the creature that applied the
  condition hits the bearer with a weapon attack (Hunter's Mark; type None = the weapon's).
- `bonus_actions`: actions the bearer may take as a bonus action ("dash": Expeditious Retreat).
- `blocks_verbal`: the bearer cannot cast spells with a verbal component (Silence).
- `turn_start_damage` / `turn_start_damage_type`: dice of damage the bearer takes at the start of
  each of its turns (burning from alchemist's fire, M27.6); `turn_end_damage` /
  `turn_end_damage_type` the same at the end of each of its turns (M29.9a: Acid Arrow's later
  acid, a one-round condition that ticks on the bearer's own turn end).
- `end_check`: `EndCheck(ability, dc, label)`: a creature in the bearer's zone (the bearer too)
  may use its action to make this ability check; a success ends every instance (SRD 5.1
  Alchemist's Fire: an action and a DC 10 Dexterity check put the flames out).
- `duration`: the default `DefaultDuration(kind, rounds, tick_on)` for a new instance when the
  applying effect does not say otherwise. `srd_condition` is False for the BG3/SRD-action extras.

Public API: `AdvKey`, `DurationKey`, `BoundaryKey`, `DamageKey`, `DefaultDuration`, `EndCheck`,
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

BONUS_DICE = r"^-?\d*d\d+$"

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


class EndCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ability: AbilityKey
    dc: int = Field(ge=1)
    label: str = Field(min_length=1)


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
    ac_bonus: int = 0
    ac_floor: int | None = Field(default=None, ge=1)
    attack_dice: str | None = Field(default=None, pattern=BONUS_DICE)
    save_dice: str | None = Field(default=None, pattern=BONUS_DICE)
    check_dice: str | None = Field(default=None, pattern=BONUS_DICE)
    consumed_by_attack: bool = False
    ends_on_damage: bool = False
    ends_on_source_side_harm: bool = False
    unseen: bool = False
    sightless: bool = False
    speed_bonus: int = Field(default=0, ge=0)
    damage_resistances: tuple[DamageKey, ...] = ()
    source_rider_dice: str | None = Field(default=None, pattern=r"^\d*d\d+$")
    source_rider_type: DamageKey | None = None
    bonus_actions: tuple[Literal["dash", "disengage", "hide"], ...] = ()
    blocks_verbal: bool = False
    turn_start_damage: str | None = Field(default=None, pattern=r"^\d*d\d+([+-]\d+)?$")
    turn_start_damage_type: DamageKey | None = None
    turn_end_damage: str | None = Field(default=None, pattern=r"^\d*d\d+([+-]\d+)?$")
    turn_end_damage_type: DamageKey | None = None
    end_check: EndCheck | None = None
    duration: DefaultDuration = DefaultDuration()

    @model_validator(mode="after")
    def _check_turn_damage(self) -> ConditionDef:
        if (self.turn_start_damage is None) != (self.turn_start_damage_type is None):
            raise ValueError("turn_start_damage and turn_start_damage_type go together")
        if (self.turn_end_damage is None) != (self.turn_end_damage_type is None):
            raise ValueError("turn_end_damage and turn_end_damage_type go together")
        return self


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
