"""Surface definitions: the schema of data/bg3/surfaces.json and its loader (SPEC 7.2 surfaces).

A surface (fire, oil, water, ice, a poison cloud, a spell's web or fog) lies in a ZONE
(`aidm.models.zones.ZoneSurface`). Everything it does is DATA read by ONE interpreter
(`aidm.rules.surfaces`); there is never a per-surface branch in code.

`SurfaceDef` fields:
- `index`, `name`; `duration_rounds` (the default lifetime when the placing effect gives none;
  None = until removed); `dc` (the save DC when the placed surface carries none, e.g. an
  environmental oil slick; spell surfaces carry the caster's DC).
- `difficult`: the zone counts as difficult terrain while the surface lies there.
- `affects`: "all" or "hostile_to_source" (only creatures on another side than the surface's
  source, e.g. a guardian aura).
- `follows_source`: the surface moves with its source creature (an aura).
- `harms`: `SurfaceHarm` entries applied to a creature at the listed moments.

`SurfaceHarm(when, save, dc, half_on_save, damage, damage_type, upcast_dice, condition,
condition_rounds, while_inside)`: `when` lists "create" (every creature in the zone when the
surface appears), "enter" (a creature moves into the zone) and "turn_start" (a creature starts
its turn there). With a `save` the creature saves first: on a success nothing happens, or half
damage when `half_on_save`. `damage` dice (+ `upcast_dice` per slot level above the spell's
level) of `damage_type`; `condition` for `condition_rounds` (None = the condition's default).
`while_inside` conditions last while the creature stays (they are re-applied at each turn
start, end when it leaves and when the surface goes away), e.g. blinded inside a fog.

`SurfaceInteraction(surfaces | surface + damage_type, consumes, creates, burst)`: what happens
when a surface meets another one in a zone (`surfaces`: an unordered pair, checked when one of
them is placed where the other lies) or when damage of `damage_type` hits a creature or an area
in a zone holding `surface`. `consumes` are removed (an incoming consumed surface is never
placed), `creates` are placed with their default duration, and `burst` (a `SurfaceHarm`; its
`when` is ignored) hits every creature in the zone once.

Public API: the models above, `SurfaceData(surfaces, interactions)`,
`load_surface_data(path=None) -> SurfaceData` (validates every surface and condition key),
`surface_data()` (default file, cached), `surface_defs() -> Registry[SurfaceDef]` (cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.data.ac_formulas import AbilityKey
from aidm.data.condition_defs import DamageKey, condition_defs
from aidm.data.registry import Registry

DEFAULT_SURFACES = Path(__file__).resolve().parents[2] / "data" / "bg3" / "surfaces.json"
DEFAULT_SURFACE_DC = 12

type SurfaceMoment = Literal["create", "enter", "turn_start"]


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SurfaceHarm(_Strict):
    when: tuple[SurfaceMoment, ...] = ("enter", "turn_start")
    save: AbilityKey | None = None
    dc: int | None = Field(default=None, ge=1)
    half_on_save: bool = False
    damage: str | None = None
    damage_type: DamageKey | None = None
    upcast_dice: str | None = None
    condition: str | None = None
    condition_rounds: int | None = Field(default=None, ge=1)
    while_inside: bool = False

    @model_validator(mode="after")
    def _check_harm(self) -> SurfaceHarm:
        if (self.damage is None) != (self.damage_type is None):
            raise ValueError("damage and damage_type go together")
        if self.damage is None and self.condition is None:
            raise ValueError("a harm needs damage or a condition")
        if self.half_on_save and (self.save is None or self.damage is None):
            raise ValueError("half_on_save needs a save and damage")
        if self.while_inside and (self.condition is None or self.condition_rounds is not None):
            raise ValueError("while_inside needs a condition and no condition_rounds")
        return self


class SurfaceDef(_Strict):
    index: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1)
    duration_rounds: int | None = Field(default=None, ge=1)
    dc: int = Field(default=DEFAULT_SURFACE_DC, ge=1)
    difficult: bool = False
    affects: Literal["all", "hostile_to_source"] = "all"
    follows_source: bool = False
    harms: tuple[SurfaceHarm, ...] = ()


class SurfaceInteraction(_Strict):
    surfaces: tuple[str, str] | None = None
    surface: str | None = None
    damage_type: DamageKey | None = None
    consumes: tuple[str, ...] = ()
    creates: tuple[str, ...] = ()
    burst: SurfaceHarm | None = None

    @model_validator(mode="after")
    def _check_trigger(self) -> SurfaceInteraction:
        pair = self.surfaces is not None
        if pair == (self.surface is not None or self.damage_type is not None):
            raise ValueError("give either `surfaces` or `surface` + `damage_type`")
        if not pair and (self.surface is None or self.damage_type is None):
            raise ValueError("a damage interaction needs `surface` and `damage_type`")
        if self.surfaces is not None and self.surfaces[0] == self.surfaces[1]:
            raise ValueError("a surface does not interact with itself")
        if not set(self.consumes) <= set(self.involved()):
            raise ValueError("an interaction can only consume the surfaces involved")
        if self.burst is not None and self.burst.save is not None and self.burst.dc is None:
            raise ValueError("a burst with a save needs its own dc")
        return self

    def involved(self) -> tuple[str, ...]:
        if self.surfaces is not None:
            return self.surfaces
        return (self.surface,) if self.surface is not None else ()


class SurfaceData(_Strict):
    surfaces: tuple[SurfaceDef, ...]
    interactions: tuple[SurfaceInteraction, ...] = ()


def _harms(data: SurfaceData) -> list[SurfaceHarm]:
    found = [harm for surface in data.surfaces for harm in surface.harms]
    found.extend(i.burst for i in data.interactions if i.burst is not None)
    return found


def _check_references(data: SurfaceData) -> None:
    kinds = {s.index for s in data.surfaces}
    if len(kinds) != len(data.surfaces):
        raise ValueError("duplicate surface index")
    for interaction in data.interactions:
        unknown = set(interaction.involved()) | set(interaction.creates)
        if unknown - kinds:
            raise ValueError(f"interaction names unknown surfaces {sorted(unknown - kinds)}")
    conditions = condition_defs()
    for harm in _harms(data):
        if harm.condition is not None and harm.condition not in conditions:
            raise ValueError(f"surface harm names unknown condition {harm.condition!r}")


def load_surface_data(path: Path | None = None) -> SurfaceData:
    target = path if path is not None else DEFAULT_SURFACES
    data = SurfaceData.model_validate(json.loads(target.read_text(encoding="utf-8")))
    _check_references(data)
    return data


@functools.cache
def surface_data() -> SurfaceData:
    return load_surface_data()


@functools.cache
def surface_defs() -> Registry[SurfaceDef]:
    return Registry(surface_data().surfaces)
