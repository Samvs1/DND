"""Spell effect DSL: the schema of data/bg3/spells/<index>.json and its loader (SPEC 7.4).

Every shipped spell is ONE JSON file read by ONE generic interpreter (`aidm.rules.spell_effects`
via `aidm.rules.spells.cast_spell`); there is never a per-spell branch in code. Spells the DSL
cannot express are not shipped (M3.6 lists them in docs/RULES_DECISIONS.md). The authoring guide
is in docs/DECISIONS.md ("Spell DSL authoring guide").

`SpellDef` fields:
- `index`: the SRD spell index (also the file name); `level` 0-9 (0 = cantrip); `school`;
  `classes` (class indexes whose lists include it); `casting_time` action / bonus_action /
  reaction (reactions are Tier 2: refused at cast time).
- `range`: `SpellRange(kind, feet)`: self, touch (same zone) or feet (zone range band).
- `concentration` and `duration_rounds` (1 minute = 10 rounds; None = instantaneous).
- `targeting`: `Targeting(kind, count, count_per_slot, count_by_character_level, repeat, area)`:
  "self"; "creature" (one creature); "creatures" (up to `count` + `count_per_slot` per slot
  level above the spell's level, or the `count_by_character_level` table: distinct creatures,
  or with `repeat` exactly that many instances spread round-robin over the chosen creatures,
  like darts and beams); "area" (every creature except the caster in the chosen zone, or the
  caster's zone for range self; `area` "zone_and_adjacent" adds the neighbouring zones). This
  block is how multi-targeting by count or area is expressed.
- `effects`: ordered `Effect`s run for each target instance (area spells share one roll per
  damage/heal effect across targets, SRD).

Effects (`type` tag):
- `attack_roll(attack: melee|ranged, on_hit)`: a spell attack; `on_hit` runs on a hit, a
  critical hit doubles its damage dice.
- `save(ability, on_fail, on_success)`: the target saves against the caster's spell DC;
  `on_success` is "none", "half" (the `on_fail` damage halved, its other effects skipped) or a
  list of effects.
- `damage(dice, damage_type, add_modifier, upcast_dice, cantrip_scaling)`: `upcast_dice` is added
  once per slot level above the spell's level; `cantrip_scaling` multiplies the dice count at
  character levels 5, 11 and 17.
- `heal(dice, add_modifier, upcast_dice)`: `add_modifier` adds the spellcasting modifier.
- `temp_hp(dice, add_modifier, upcast_dice)`: temporary HP (never stacking).
- `apply_condition(condition, rounds, save_ends)`; `remove_condition(conditions)`;
  `ac_buff(condition, rounds)`: a condition whose data entry carries `ac_bonus` (the amount
  lives in data/bg3/conditions.json so the sheet shows it). `rounds` None = the spell's
  `duration_rounds`, else the condition's default.
- `surface(surface, rounds)`: a surface on the target's zone (effects arrive in M3.7).
- `multi_target(area, include_target, effects)`: a splash: `effects` run on every other
  creature in the current target's zone (or zone and neighbours), sharing rolls.

Public API: the models above, `Effect` (annotated union), `load_spell_defs(directory=None) ->
Registry[SpellDef]` (one file per spell; the file stem must equal the index), `spell_defs()`
(default directory, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.data.ac_formulas import AbilityKey
from aidm.data.condition_defs import DamageKey
from aidm.data.registry import Registry

DEFAULT_SPELL_DIR = Path(__file__).resolve().parents[2] / "data" / "bg3" / "spells"

type AreaKey = Literal["zone", "zone_and_adjacent"]


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SpellRange(_Strict):
    kind: Literal["self", "touch", "feet"]
    feet: int | None = Field(default=None, ge=5)

    @model_validator(mode="after")
    def _check_feet(self) -> SpellRange:
        if (self.kind == "feet") != (self.feet is not None):
            raise ValueError("feet is required for, and only for, kind 'feet'")
        return self


class Targeting(_Strict):
    kind: Literal["self", "creature", "creatures", "area"]
    count: int = Field(default=1, ge=1)
    count_per_slot: int = Field(default=0, ge=0)
    count_by_character_level: dict[int, int] = Field(default_factory=dict[int, int])
    repeat: bool = False
    area: AreaKey | None = None

    @model_validator(mode="after")
    def _check_area(self) -> Targeting:
        if (self.kind == "area") != (self.area is not None):
            raise ValueError("area is required for, and only for, kind 'area'")
        return self


class AttackRollEffect(_Strict):
    type: Literal["attack_roll"] = "attack_roll"
    attack: Literal["melee", "ranged"]
    on_hit: tuple[Effect, ...] = Field(min_length=1)


class SaveEffect(_Strict):
    type: Literal["save"] = "save"
    ability: AbilityKey
    on_fail: tuple[Effect, ...] = Field(min_length=1)
    on_success: Literal["none", "half"] | tuple[Effect, ...] = "none"


class DamageEffect(_Strict):
    type: Literal["damage"] = "damage"
    dice: str = Field(min_length=1)
    damage_type: DamageKey
    add_modifier: bool = False
    upcast_dice: str | None = None
    cantrip_scaling: bool = False


class HealEffect(_Strict):
    type: Literal["heal"] = "heal"
    dice: str = Field(min_length=1)
    add_modifier: bool = True
    upcast_dice: str | None = None


class TempHpEffect(_Strict):
    type: Literal["temp_hp"] = "temp_hp"
    dice: str = Field(min_length=1)
    add_modifier: bool = False
    upcast_dice: str | None = None


class ApplyConditionEffect(_Strict):
    type: Literal["apply_condition"] = "apply_condition"
    condition: str = Field(min_length=1)
    rounds: int | None = Field(default=None, ge=1)
    save_ends: AbilityKey | None = None


class RemoveConditionEffect(_Strict):
    type: Literal["remove_condition"] = "remove_condition"
    conditions: tuple[str, ...] = Field(min_length=1)


class AcBuffEffect(_Strict):
    type: Literal["ac_buff"] = "ac_buff"
    condition: str = Field(min_length=1)
    rounds: int | None = Field(default=None, ge=1)


class SurfaceEffect(_Strict):
    type: Literal["surface"] = "surface"
    surface: str = Field(min_length=1)
    rounds: int | None = Field(default=None, ge=1)


class MultiTargetEffect(_Strict):
    type: Literal["multi_target"] = "multi_target"
    area: AreaKey = "zone"
    include_target: bool = False
    effects: tuple[Effect, ...] = Field(min_length=1)


Effect = Annotated[
    AttackRollEffect
    | SaveEffect
    | DamageEffect
    | HealEffect
    | TempHpEffect
    | ApplyConditionEffect
    | RemoveConditionEffect
    | AcBuffEffect
    | SurfaceEffect
    | MultiTargetEffect,
    Field(discriminator="type"),
]


class SpellDef(_Strict):
    index: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")
    level: int = Field(ge=0, le=9)
    school: str = Field(min_length=1)
    classes: tuple[str, ...] = Field(min_length=1)
    casting_time: Literal["action", "bonus_action", "reaction"] = "action"
    range: SpellRange
    concentration: bool = False
    duration_rounds: int | None = Field(default=None, ge=1)
    targeting: Targeting
    effects: tuple[Effect, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_spell(self) -> SpellDef:
        if self.concentration and self.duration_rounds is None:
            raise ValueError("a concentration spell needs duration_rounds")
        if self.targeting.kind == "self" and self.range.kind != "self":
            raise ValueError("self targeting needs range 'self'")
        if self.level > 0 and self.targeting.count_by_character_level:
            raise ValueError("count_by_character_level is for cantrips only")
        if self.level == 0 and self.targeting.count_per_slot:
            raise ValueError("count_per_slot needs a levelled spell")
        return self


for _model in (AttackRollEffect, SaveEffect, MultiTargetEffect, SpellDef):
    _model.model_rebuild()


def load_spell_defs(directory: Path | None = None) -> Registry[SpellDef]:
    root = directory if directory is not None else DEFAULT_SPELL_DIR
    spells: list[SpellDef] = []
    for path in sorted(root.glob("*.json")):
        spell = SpellDef.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if spell.index != path.stem:
            raise ValueError(f"{path.name}: index {spell.index!r} must match the file name")
        spells.append(spell)
    return Registry(spells)


@functools.cache
def spell_defs() -> Registry[SpellDef]:
    return load_spell_defs()
