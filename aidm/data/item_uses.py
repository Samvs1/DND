"""Item uses: the schema of data/bg3/item_uses.json and its validating loader (GOAL_ITEMS, M27.1).

Every usable catalogue item lists its uses as DATA. ONE interpreter (M27.2, `aidm.rules.item_use`)
reads them; there is never a per-item branch. The schema lives here because `aidm.models` and
`aidm.data` are sibling layers (they may not import each other) and the loader must check the
catalogue, surfaces, spells and skills.

`ItemUse(id, item, verbs, when, tags, label, effect, cost, consumes, charges, tool, noise)`:
- `item`: a catalogue id, or the family `scroll-of-*` (every spell scroll).
- `when`: dark_place | locked | place | fight | ally_down | long_rest | tagged_place (`tags` lists
  the terrain tags that qualify, e.g. water).
- `cost`: the action a use takes in a fight (None = free or out of a fight only).
- `consumes`: one is used up; `charges`: uses per inventory entry (healer's kit); never both.
- `tool`: an SRD tool, proficiency applies. `noise`: the place becomes alerted.
- `effect`: a closed union keyed by `kind`: light_place, boon, surface, damage, condition,
  unlock, supplies, stabilize, craft, cast_spell, reveal_map.

`ScrollPower(level, save_dc, attack_bonus)`: the SRD 5.1 Spell Scroll table, stored as data.

Public API: the models above, `ItemUseData(uses, scroll_table)`, `ItemUseError` (names the bad
entry), `load_item_use_data(path=None)`, `item_use_data()` (cached), `uses_for_item(item)`.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from aidm.data.ac_formulas import AbilityKey
from aidm.data.condition_defs import DamageKey, condition_defs
from aidm.data.item_catalogue import SCROLL_PREFIX, item_catalogue
from aidm.data.spell_defs import shipped_spell_ids
from aidm.data.srd import srd
from aidm.data.surface_defs import surface_defs

DEFAULT_ITEM_USES = Path(__file__).resolve().parents[2] / "data" / "bg3" / "item_uses.json"
SCROLL_FAMILY = SCROLL_PREFIX + "*"
DICE_PATTERN = r"^[1-9][0-9]*d[0-9]+([+-][0-9]+)?$"

type UseWhen = Literal[
    "dark_place", "locked", "place", "fight", "ally_down", "long_rest", "tagged_place"
]
type UseCost = Literal["action", "bonus"]
type LightReachKey = Literal["zone", "touching"]  # mirrors aidm.models.world.LightReach
type BoonScope = Literal["place", "until_long_rest"]


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LightPlace(_Strict):
    kind: Literal["light_place"]
    skills: tuple[str, ...] = ()  # advantage on these skills while the place is lit by it
    reach: LightReachKey = "touching"  # M27.2: own zone + touching zones; "zone" = own only


class Boon(_Strict):
    kind: Literal["boon"]
    skills: tuple[str, ...] = ()
    saves_against: tuple[str, ...] = ()  # damage or condition names, e.g. "poison"
    scope: BoonScope = "place"

    @model_validator(mode="after")
    def _check_boon(self) -> Boon:
        if not self.skills and not self.saves_against:
            raise ValueError("a boon needs skills or saves_against")
        return self


class SurfaceUse(_Strict):
    kind: Literal["surface"]
    surface: str = Field(min_length=1)


class DamageUse(_Strict):
    kind: Literal["damage"]
    roll: Literal["attack", "save"] = "attack"
    dice: str = Field(pattern=DICE_PATTERN)
    damage_type: DamageKey
    save: AbilityKey | None = None
    creature_types: tuple[str, ...] = ()  # empty = any creature

    @model_validator(mode="after")
    def _check_damage(self) -> DamageUse:
        if (self.roll == "save") != (self.save is not None):
            raise ValueError("a save damage use names its save, an attack one does not")
        return self


class ConditionUse(_Strict):
    kind: Literal["condition"]
    condition: str = Field(min_length=1)
    rounds: int | None = Field(default=None, ge=1)


class Unlock(_Strict):
    kind: Literal["unlock"]
    method: Literal["key", "pick", "force"]
    ability: AbilityKey | None = None
    skill: str | None = None
    advantage: bool = False


class Supplies(_Strict):
    kind: Literal["supplies"]
    skill: str
    amount: int = Field(ge=1)


class Stabilize(_Strict):
    kind: Literal["stabilize"]


class Craft(_Strict):
    kind: Literal["craft"]
    supplies: int = Field(ge=1)  # camp supplies spent
    output: str = Field(min_length=1)  # catalogue item made


class CastSpell(_Strict):
    kind: Literal["cast_spell"]
    spell: str | None = None  # None: the spell named by the scroll's own id


class RevealMap(_Strict):
    kind: Literal["reveal_map"]


type UseEffect = Annotated[
    LightPlace
    | Boon
    | SurfaceUse
    | DamageUse
    | ConditionUse
    | Unlock
    | Supplies
    | Stabilize
    | Craft
    | CastSpell
    | RevealMap,
    Field(discriminator="kind"),
]


class ItemUse(_Strict):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")
    item: str = Field(min_length=1)
    verbs: tuple[str, ...] = Field(min_length=1)
    when: UseWhen
    tags: tuple[str, ...] = ()
    label: str = Field(min_length=1)
    effect: UseEffect
    cost: UseCost | None = None
    consumes: bool = False
    charges: int | None = Field(default=None, ge=1)
    tool: bool = False
    noise: bool = False

    @model_validator(mode="after")
    def _check_use(self) -> ItemUse:
        if self.consumes and self.charges is not None:
            raise ValueError("a use consumes the item or has charges, not both")
        if (self.when == "tagged_place") != bool(self.tags):
            raise ValueError("tags go with when=tagged_place and only then")
        return self


class ScrollPower(_Strict):
    level: int = Field(ge=0, le=9)
    save_dc: int = Field(ge=1)
    attack_bonus: int


class ItemUseData(_Strict):
    uses: tuple[ItemUse, ...]
    scroll_table: tuple[ScrollPower, ...]

    def scroll_power(self, level: int) -> ScrollPower:
        return next(row for row in self.scroll_table if row.level == level)


class ItemUseError(ValueError):
    """A bad item_uses.json entry; `entry` is the use id (or `scroll_table`)."""

    def __init__(self, entry: str, problem: str) -> None:
        super().__init__(f"item use {entry!r}: {problem}")
        self.entry = entry
        self.problem = problem


def _effect_problems(effect: UseEffect) -> list[str]:
    skills = {s.index for s in srd().skills.all()}
    names: list[str] = []
    if isinstance(effect, LightPlace | Boon):
        names = list(effect.skills)
    elif isinstance(effect, Supplies):
        names = [effect.skill]
    elif isinstance(effect, Unlock) and effect.skill is not None:
        names = [effect.skill]
    problems = [f"unknown skill {n!r}" for n in names if n not in skills]
    if isinstance(effect, SurfaceUse) and effect.surface not in surface_defs():
        problems.append(f"unknown surface {effect.surface!r}")
    if isinstance(effect, ConditionUse) and effect.condition not in condition_defs():
        problems.append(f"unknown condition {effect.condition!r}")
    if isinstance(effect, CastSpell) and effect.spell and effect.spell not in shipped_spell_ids():
        problems.append(f"unknown spell {effect.spell!r}")
    if isinstance(effect, Craft) and effect.output not in item_catalogue():
        problems.append(f"unknown item {effect.output!r}")
    return problems


def _use_problems(use: ItemUse) -> list[str]:
    problems = _effect_problems(use.effect)
    if use.item != SCROLL_FAMILY and use.item not in item_catalogue():
        problems.append(f"unknown item {use.item!r}")
    return problems


def _check(data: ItemUseData) -> None:
    seen: set[str] = set()
    for use in data.uses:
        if use.id in seen:
            raise ItemUseError(use.id, "duplicate use id")
        seen.add(use.id)
        problems = _use_problems(use)
        if problems:
            raise ItemUseError(use.id, "; ".join(problems))
    if sorted(r.level for r in data.scroll_table) != list(range(10)):
        raise ItemUseError("scroll_table", "needs exactly one row per spell level 0 to 9")


def _entry_name(raw: object, error: ValidationError) -> str:
    first = error.errors()[0]["loc"]
    uses = raw.get("uses") if isinstance(raw, dict) else None
    if first[:1] == ("uses",) and isinstance(uses, list) and isinstance(first[1], int):
        entry = uses[first[1]] if first[1] < len(uses) else {}
        return str(entry.get("id", first[1])) if isinstance(entry, dict) else str(first[1])
    return str(first[0]) if first else "file"


def load_item_use_data(path: Path | None = None) -> ItemUseData:
    target = path if path is not None else DEFAULT_ITEM_USES
    raw = json.loads(target.read_text(encoding="utf-8"))
    try:
        data = ItemUseData.model_validate(raw)
    except ValidationError as error:
        raise ItemUseError(_entry_name(raw, error), str(error.errors()[0]["msg"])) from error
    _check(data)
    return data


@functools.cache
def item_use_data() -> ItemUseData:
    return load_item_use_data()


def uses_for_item(item: str) -> tuple[ItemUse, ...]:
    """Uses of a catalogue item id; every `scroll-of-*` item gets the scroll family's uses."""
    key = SCROLL_FAMILY if item.startswith(SCROLL_PREFIX) else item
    return tuple(u for u in item_use_data().uses if u.item == key)
