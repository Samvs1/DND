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
- `from_light` (M27.6): the use is made with the hero's carried LIT light of this item (a lit
  torch thrown); it ends that light instead of consuming an inventory item.
- `improvised` (M27.6): the one use of a carried item with no listed use: an SRD improvised
  weapon throw (`DamageUse.ability_mod`: the thrower's STR modifier is added); `item` is "*".
- `substances` (M27.6): catalogue id -> what the item delivers on a hit (water, fire, acid,
  holy, silver, oil); `aidm.rules.weaknesses` applies a target's weakness to it.
- `effect`: a closed union keyed by `kind`: light_place, boon, surface, damage (an optional
  `condition` on a hit), condition, unlock, supplies, stabilize, craft, cast_spell, reveal_map,
  ignite (damage of a type into a zone, only through the surfaces' damage interactions),
  unpack (a sealed equipment pack becomes its SRD contents, M29.3b).

`ScrollPower(level, save_dc, attack_bonus)`: the SRD 5.1 Spell Scroll table, stored as data.

Public API: the models above, `ItemUseData(uses, scroll_table)`, `ItemUseError` (names the bad
entry), `load_item_use_data(path=None)`, `item_use_data()` (cached), `uses_for_item(item)`,
`improvised_use(item)`, `item_substances(item)`, `Substance`, `SUBSTANCES` (its names).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from aidm.data.ac_formulas import AbilityKey
from aidm.data.condition_defs import DamageKey, condition_defs
from aidm.data.item_catalogue import SCROLL_PREFIX, item_catalogue
from aidm.data.spell_defs import shipped_spell_ids
from aidm.data.srd import srd
from aidm.data.srd_equipment import pack_items
from aidm.data.surface_defs import surface_defs

DEFAULT_ITEM_USES = Path(__file__).resolve().parents[2] / "data" / "bg3" / "item_uses.json"
SCROLL_FAMILY = SCROLL_PREFIX + "*"
DICE_PATTERN = r"^[1-9][0-9]*(d[0-9]+([+-][0-9]+)?)?$"  # dice, or a flat amount ("1")
IMPROVISED_ITEM = "*"  # the improvised use stands for any item (M27.6)

type UseWhen = Literal[
    "dark_place", "locked", "place", "fight", "ally_down", "long_rest", "tagged_place"
]
type UseCost = Literal["action", "bonus"]
type LightReachKey = Literal["zone", "touching"]  # mirrors aidm.models.world.LightReach
type BoonScope = Literal["place", "until_long_rest"]
type Substance = Literal["water", "fire", "acid", "holy", "silver", "oil"]
SUBSTANCES: frozenset[str] = frozenset(get_args(Substance.__value__))


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LightPlace(_Strict):
    kind: Literal["light_place"]
    skills: tuple[str, ...] = ()  # advantage on these skills while its light lasts (M27.12)
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
    condition: str | None = None  # applied on a hit (alchemist's fire: burning, M27.6)
    ability_mod: bool = False  # adds the thrower's STR modifier (SRD improvised weapon, M27.6)

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


class Ignite(_Strict):
    """Damage of this type into a zone (M27.6): only what the surfaces' damage interactions
    make of it (a thrown torch into oil sets it alight); nothing else is harmed."""

    kind: Literal["ignite"]
    damage_type: DamageKey = "fire"


class Unpack(_Strict):
    """Open a sealed equipment pack into its SRD 5.1 contents (M29.3b, old saves)."""

    kind: Literal["unpack"]


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
    | RevealMap
    | Ignite
    | Unpack,
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
    from_light: bool = False  # M27.6: uses the hero's carried LIT light of this item, ending it

    @model_validator(mode="after")
    def _check_use(self) -> ItemUse:
        if self.consumes and self.charges is not None:
            raise ValueError("a use consumes the item or has charges, not both")
        if self.from_light and (self.consumes or self.charges is not None):
            raise ValueError("a from_light use ends the light; it consumes nothing else")
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
    improvised: ItemUse  # M27.6: any carried item without a listed use, thrown (item "*")
    substances: dict[str, tuple[Substance, ...]] = Field(
        default_factory=dict[str, tuple[Substance, ...]]
    )  # M27.6: what an item delivers on a hit (catalogue id -> substances)

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
    elif isinstance(effect, Supplies | Unlock) and effect.skill is not None:
        names = [effect.skill]
    problems = [f"unknown skill {n!r}" for n in names if n not in skills]
    if isinstance(effect, SurfaceUse) and effect.surface not in surface_defs():
        problems.append(f"unknown surface {effect.surface!r}")
    if (
        isinstance(effect, ConditionUse | DamageUse)
        and effect.condition is not None
        and effect.condition not in condition_defs()
    ):
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
    if isinstance(use.effect, Unpack) and not pack_items(srd().equipment.find(use.item)):
        problems.append(f"{use.item!r} is not an equipment pack")
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
    if data.improvised.item != IMPROVISED_ITEM:
        raise ItemUseError(data.improvised.id, f"the improvised use's item is {IMPROVISED_ITEM!r}")
    for item in data.substances:
        if item not in item_catalogue():
            raise ItemUseError("substances", f"unknown item {item!r}")
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


def improvised_use(item: str) -> ItemUse:
    """The SRD improvised throw (1d4 + STR, 20/60 ft) of a carried item without a listed use."""
    return item_use_data().improvised.model_copy(update={"item": item})


def item_substances(item: str) -> tuple[Substance, ...]:
    return item_use_data().substances.get(item, ())
