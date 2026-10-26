"""Class definition schema and the data/bg3/classes/*.json loader (levels 1 to 5).

One JSON file per class, one `ClassDef` per file. Everything is data: the creation pipeline
(M2.2), slot model (M2.3), feature hooks (M2.4) and level-up (M2.5) read it, none of it is
branched on in code. Ids in `features` are SRD feature indexes, or `bg3-...` ids declared in the
class's own `bg3_features` (BG3 deltas, original wording).

Fields of `ClassDef`:
- `hit_die`, `primary_abilities`, `saving_throws`: SRD values. `armor`, `weapons`, `tools` are SRD
  proficiency indexes (categories such as `light-armor` or `simple-weapons`, or single items).
- `skill_choice`: choose N skills from the listed skill indexes (SRD skills registry).
- `equipment`: `fixed` items plus `choices`; each choice is a group whose `options` are item lists
  (pick exactly one option). Every item is an SRD equipment index.
- `spellcasting`: ability, kind (`known`, `prepared`, `pact`), `first_level`, `spellbook_start`
  (spells in a level-1 spellbook; wizard 6, SRD) and `spellbook_per_level` (spells added to the
  book on each later level; wizard 2, SRD); None for non-casters.
- `levels`: exactly levels 1 to 5. `slots` holds the slot count per spell level 1 to 5 (for a `pact`
  caster these are the pact slots: all of one spell level), `cantrips_known`, `spells_known`
  (known/pact casters only) and `asi` (an Ability Score Improvement level).
- `subclass_level`, `subclass_index`, `subclass_features`: the SRD subclass and its early features.
- `choices`: list-valued picks (fighting style, Hunter's Prey option) at a given level.

Public API: `ClassDef` and its parts, `load_class_defs(directory=None) -> Registry[ClassDef]`
(order: fighter, rogue, wizard, cleric, ranger, warlock), `class_defs()` (default, cached).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.data.ac_formulas import AbilityKey
from aidm.data.char_common import ItemQty, PickList
from aidm.data.registry import Registry

type SpellcastingKind = Literal["known", "prepared", "pact"]
type ChoiceKind = Literal["fighting_style", "subclass_option"]

MAX_CLASS_LEVEL = 5
CLASS_ORDER = ("fighter", "rogue", "wizard", "cleric", "ranger", "warlock")
DEFAULT_CLASSES_DIR = Path(__file__).resolve().parents[2] / "data" / "bg3" / "classes"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EquipChoice(_Frozen):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    options: tuple[tuple[ItemQty, ...], ...] = Field(min_length=2)


class StartingEquipment(_Frozen):
    fixed: tuple[ItemQty, ...] = ()
    choices: tuple[EquipChoice, ...] = ()


class SpellcastingDef(_Frozen):
    ability: AbilityKey
    kind: SpellcastingKind
    first_level: int = Field(ge=1, le=MAX_CLASS_LEVEL)
    spellbook_start: int = Field(default=0, ge=0)
    spellbook_per_level: int = Field(default=0, ge=0)


class ClassLevelDef(_Frozen):
    level: int = Field(ge=1, le=MAX_CLASS_LEVEL)
    features: tuple[str, ...] = ()
    cantrips_known: int = Field(default=0, ge=0)
    spells_known: int | None = Field(default=None, ge=0)
    slots: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0)
    asi: bool = False


class LevelFeatures(_Frozen):
    level: int = Field(ge=1, le=MAX_CLASS_LEVEL)
    features: tuple[str, ...] = Field(min_length=1)


class ClassChoice(_Frozen):
    id: str = Field(min_length=1)
    level: int = Field(ge=1, le=MAX_CLASS_LEVEL)
    kind: ChoiceKind
    pick: PickList


class Bg3Feature(_Frozen):
    id: str = Field(pattern=r"^bg3-[a-z0-9-]+$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    note: str = Field(min_length=1)


class ClassDef(_Frozen):
    index: str = Field(min_length=1)
    name: str = Field(min_length=1)
    hit_die: int = Field(ge=4, le=12)
    primary_abilities: tuple[AbilityKey, ...] = Field(min_length=1)
    saving_throws: tuple[AbilityKey, AbilityKey]
    armor: tuple[str, ...] = ()
    weapons: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    skill_choice: PickList
    equipment: StartingEquipment
    spellcasting: SpellcastingDef | None = None
    subclass_level: int = Field(ge=1, le=MAX_CLASS_LEVEL)
    subclass_index: str = Field(min_length=1)
    subclass_features: tuple[LevelFeatures, ...] = ()
    levels: tuple[ClassLevelDef, ...]
    choices: tuple[ClassChoice, ...] = ()
    bg3_features: tuple[Bg3Feature, ...] = ()

    @model_validator(mode="after")
    def _check_levels(self) -> ClassDef:
        if tuple(row.level for row in self.levels) != tuple(range(1, MAX_CLASS_LEVEL + 1)):
            raise ValueError(f"{self.index}: levels must be exactly 1..{MAX_CLASS_LEVEL}")
        if self.spellcasting is None:
            if any(
                r.cantrips_known or r.spells_known is not None or any(r.slots) for r in self.levels
            ):
                raise ValueError(f"{self.index}: spell data on a non-caster")
        elif self.spellcasting.kind == "prepared" and any(
            r.spells_known is not None for r in self.levels
        ):
            raise ValueError(f"{self.index}: prepared casters have no spells_known")
        elif self.spellcasting.kind != "prepared" and any(
            r.spells_known is None for r in self.levels
        ):
            raise ValueError(f"{self.index}: known/pact casters need spells_known on every level")
        return self

    @model_validator(mode="after")
    def _check_bg3_ids(self) -> ClassDef:
        declared = {f.id for f in self.bg3_features}
        used = {f for row in self.levels for f in row.features if f.startswith("bg3-")}
        used |= {f for lf in self.subclass_features for f in lf.features if f.startswith("bg3-")}
        if used != declared:
            raise ValueError(f"{self.index}: bg3 feature ids used {used} but declared {declared}")
        return self

    def level(self, level: int) -> ClassLevelDef:
        return self.levels[level - 1]


def load_class_defs(directory: Path | None = None) -> Registry[ClassDef]:
    base = directory if directory is not None else DEFAULT_CLASSES_DIR
    entries: list[ClassDef] = []
    for path in sorted(base.glob("*.json")):
        entry = ClassDef.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if entry.index != path.stem:
            raise ValueError(f"{path.name}: index {entry.index!r} must match the file name")
        entries.append(entry)
    rank = {key: i for i, key in enumerate(CLASS_ORDER)}
    entries.sort(key=lambda e: (rank.get(e.index, len(rank)), e.index))
    return Registry(entries)


@functools.cache
def class_defs() -> Registry[ClassDef]:
    return load_class_defs()
