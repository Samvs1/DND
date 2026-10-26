"""Race overlay schema and the data/bg3/races.json loader (thin overlay over SRD races).

Each `RaceDef` names an SRD race index and repeats the numbers the creation pipeline needs
(ability bonuses, speed, size, darkvision, granted proficiencies, languages, trait ids) so rules
never re-parse the SRD's nested JSON. A test pins every copied number to the SRD.

- `ability_choice`: a pick-list of abilities that each get `ability_choice_bonus` (half-elf: two
  +1 choices on top of the fixed +2 CHA).
- `tool_choice`, `language_choices`, `skill_choice`, `cantrip_choices`: picks made at creation;
  `cantrip_class` names the class spell list the racial cantrips come from (high elf: wizard).
- Subraces are nested `SubraceDef` entries with their own SRD subrace index; their bonuses and
  traits ADD to the parent race (the pipeline combines them, M2.2).

Public API: `RaceDef`, `SubraceDef`, `AbilityBonusDef`,
`load_race_defs(path=None) -> Registry[RaceDef]`, `race_defs()` (default, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.data.ac_formulas import AbilityKey
from aidm.data.char_common import PickList
from aidm.data.registry import Registry

type SizeKey = Literal["Small", "Medium"]

DEFAULT_RACES = Path(__file__).resolve().parents[2] / "data" / "bg3" / "races.json"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AbilityBonusDef(_Frozen):
    ability: AbilityKey
    bonus: int


class _Grants(_Frozen):
    ability_bonuses: tuple[AbilityBonusDef, ...] = ()
    skills: tuple[str, ...] = ()
    weapon_proficiencies: tuple[str, ...] = ()
    tool_proficiencies: tuple[str, ...] = ()
    tool_choice: PickList | None = None
    languages: tuple[str, ...] = ()
    language_choices: int = Field(default=0, ge=0)
    cantrip_choices: int = Field(default=0, ge=0)
    cantrip_class: str | None = None
    traits: tuple[str, ...] = ()


class SubraceDef(_Grants):
    index: str = Field(min_length=1)
    name: str = Field(min_length=1)


class RaceDef(_Grants):
    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    size: SizeKey
    speed: int = Field(ge=0)
    darkvision: int = Field(default=0, ge=0)
    ability_choice: PickList | None = None
    ability_choice_bonus: int = Field(default=0, ge=0)
    skill_choice: PickList | None = None
    subraces: tuple[SubraceDef, ...] = ()


def load_race_defs(path: Path | None = None) -> Registry[RaceDef]:
    target = path if path is not None else DEFAULT_RACES
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Registry(RaceDef.model_validate(item) for item in raw)


@functools.cache
def race_defs() -> Registry[RaceDef]:
    return load_race_defs()
