"""Player-character data carried on a `Creature` (`Creature.pc`), plus size.

A PC is a `Creature` (kind PC) whose `pc` field holds everything only characters have: race,
class, background, proficiency lists, inventory, spells and the player's text. Combat, damage,
conditions and rests keep working on `Creature` alone, and a `CreatureAdded` event carrying a PC
replays like any other creature (docs/DECISIONS.md M2.2).

Public API:
- `Size`: the SRD size categories (values are the SRD spelling, "Medium").
- `InventoryItem(item, qty)`: an SRD equipment index and a count.
- `Keepsake(id, name, description, quest_id)`: a story object the hero carries (a note, a key,
  a trinket; M19.3): no gold value, cannot be sold or equipped. With a `quest_id` it is a quest
  item placed by the engine (M23); without one it is flavour.
- `Equipped(armor, shield, main_hand, off_hand, ranged)`: equipment indexes in use (None = empty).
- `PcData`: race/subrace, `class_index`, `level`, `subclass` (None until the subclass level),
  `background`, `base_abilities` (before racial bonuses), `armor_proficiencies`,
  `weapon_proficiencies`, `tool_proficiencies` (SRD proficiency indexes), `languages`,
  `features` (class and subclass feature ids), `traits` (race trait ids), `class_choices`
  (choice id -> picked option ids, e.g. a fighting style), `feature_choices` (feature id ->
  picks: expertise skills, ancestry option), `xp` (experience points), `inventory`, `equipped`,
  `gold`, `cantrips`, `race_cantrips`, `spells_known` (known/pact casters), `spellbook` (wizards),
  `prepared` (prepared casters), `portrait_id`, `pronouns`, `backstory` (<= 400 chars),
  `keepsakes`.

State models are mutable (only the reducer mutates them) and every field added later needs a
default (docs/DECISIONS.md M1.2 schema growth).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.abilities import Ability

MAX_BACKSTORY_CHARS = 400
MAX_KEEPSAKE_NAME = 40
MAX_KEEPSAKE_TEXT = 200


class Size(StrEnum):
    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    HUGE = "Huge"
    GARGANTUAN = "Gargantuan"


class InventoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str = Field(min_length=1)
    qty: int = Field(default=1, ge=1)
    charges: int | None = Field(default=None, ge=0)  # M27.1: uses left (healer's kit); None = n/a


class Keepsake(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=MAX_KEEPSAKE_NAME)
    description: str = Field(default="", max_length=MAX_KEEPSAKE_TEXT)
    quest_id: str | None = None  # M23: a quest item (engine-placed); None: flavour only
    teaches: str | None = None  # M29.9b T13: the learn tag it carries (held or read: learned)


class Equipped(BaseModel):
    model_config = ConfigDict(extra="forbid")

    armor: str | None = None
    shield: str | None = None
    main_hand: str | None = None
    off_hand: str | None = None
    ranged: str | None = None


class PcData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    race: str = Field(min_length=1)
    subrace: str | None = None
    class_index: str = Field(min_length=1)
    level: int = Field(default=1, ge=1, le=20)
    subclass: str | None = None
    background: str = Field(min_length=1)
    base_abilities: dict[Ability, int] = Field(default_factory=dict[Ability, int])
    armor_proficiencies: list[str] = Field(default_factory=list[str])
    weapon_proficiencies: list[str] = Field(default_factory=list[str])
    tool_proficiencies: list[str] = Field(default_factory=list[str])
    languages: list[str] = Field(default_factory=list[str])
    features: list[str] = Field(default_factory=list[str])
    traits: list[str] = Field(default_factory=list[str])
    class_choices: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    feature_choices: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    xp: int = Field(default=0, ge=0)
    inventory: list[InventoryItem] = Field(default_factory=list[InventoryItem])
    equipped: Equipped = Field(default_factory=Equipped)
    gold: int = Field(default=0, ge=0)
    cantrips: list[str] = Field(default_factory=list[str])
    race_cantrips: list[str] = Field(default_factory=list[str])
    spells_known: list[str] = Field(default_factory=list[str])
    spellbook: list[str] = Field(default_factory=list[str])
    prepared: list[str] = Field(default_factory=list[str])
    portrait_id: str = ""
    pronouns: str = ""
    backstory: str = Field(default="", max_length=MAX_BACKSTORY_CHARS)
    keepsakes: list[Keepsake] = Field(default_factory=list[Keepsake])
