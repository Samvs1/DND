"""The derived character sheet view model (SPEC 8): everything a player needs, read-only.

Built by `aidm.rules.sheet.build_sheet` from a PC and the registries; never stored, never an
event payload, so it can grow freely. All numbers are final (modifiers applied).

Public API:
- `AbilityLine(ability, score, modifier, save_bonus, save_proficient)`.
- `SkillLine(skill, ability, bonus, proficient, expertise)`.
- `AttackLine(name, item, hand, ability, attack_bonus, damage, damage_type, range_band,
  range_normal, range_long, hit_chance)`: `damage` is a dice expression with the modifier
  ("1d8+3"); `range_band` "melee" or "ranged"; `hit_chance` stays None (a sheet has no target;
  the hotbar preview is `aidm.rules.hit_chance.hit_chances`).
- `SlotLine(kind, current, maximum)`; `SpellLine(index, name, level, prepared, always_prepared,
  source, resource, casting_time, target_kind, target_count, count_per_slot, range_kind,
  range_feet, concentration)` (the last seven describe how the hotbar targets it, from the spell
  data; `target_count` is the count at the caster's level, plus `count_per_slot` per slot level
  above the spell's); `SpellLevelGroup(level, slots, spells)`; `SpellcastingBlock(ability,
  save_dc, attack_bonus, prepared_limit, cantrips, levels)`.
- `FeatureLine(index, name, summary, source)`; `ResourceLine(key, current, maximum, recharge)`.
- `FeatureActionLine(feature, name, economy, available, resource, uses_left, uses_max, heal,
  target_kind, range_kind, range_feet)` (M7.5b): a feature action the `feature_action` command
  runs (Second Wind, Action Surge, Breath Weapon, Turn Undead); `economy` action /
  bonus_action / extra_action; the target fields aim it like a spell.
- `InventoryLine(item, name, qty, equipped_slot, category, weight, value_gp)` (category, weight
  per item and value per item come from the item catalogue); `ConditionLine(name, rounds_left)`;
  `DeathSaveLine(successes, failures, stable, dead)`.
- `CharacterSheet`: identity (id, name, race, subrace, class, subclass, level, background, xp,
  xp_next), abilities, skills, passive_perception, proficiency_bonus, ac, hp, temp_hp, max_hp,
  speed, initiative_bonus (+DEX; BG3 rolls 1d4, `initiative_die`), attacks, attacks_per_action,
  spellcasting, features, feature_actions, resources, proficiencies and languages, resistances,
  inventory, gold, conditions, death_saves, concentrating_on (the spell being concentrated on).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from aidm.models.abilities import Ability, Skill
from aidm.models.damage import DamageType


class _Line(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AbilityLine(_Line):
    ability: Ability
    score: int
    modifier: int
    save_bonus: int
    save_proficient: bool


class SkillLine(_Line):
    skill: Skill
    ability: Ability
    bonus: int
    proficient: bool
    expertise: bool


class AttackLine(_Line):
    name: str
    item: str | None
    hand: Literal["main_hand", "off_hand", "ranged", "unarmed"]
    ability: Ability
    attack_bonus: int
    damage: str
    damage_type: DamageType
    range_band: Literal["melee", "ranged"]
    range_normal: int | None = None
    range_long: int | None = None
    hit_chance: float | None = None


class SlotLine(_Line):
    kind: Literal["standard", "pact"]
    current: int
    maximum: int


class SpellLine(_Line):
    index: str
    name: str
    level: int
    prepared: bool
    always_prepared: bool = False
    source: Literal["class", "race", "feature"] = "class"
    resource: str | None = None
    casting_time: str = "action"
    target_kind: str = "creature"
    target_count: int = 1
    count_per_slot: int = 0
    range_kind: str = "feet"
    range_feet: int | None = None
    concentration: bool = False


class SpellLevelGroup(_Line):
    level: int
    slots: list[SlotLine]
    spells: list[SpellLine]


class SpellcastingBlock(_Line):
    ability: Ability
    save_dc: int
    attack_bonus: int
    prepared_limit: int | None
    cantrips: list[SpellLine]
    levels: list[SpellLevelGroup]


class FeatureLine(_Line):
    index: str
    name: str
    summary: str
    source: Literal["class", "race"]


class FeatureActionLine(_Line):
    feature: str
    name: str
    economy: Literal["action", "bonus_action", "extra_action"]
    available: bool
    resource: str | None = None
    uses_left: int | None = None
    uses_max: int | None = None
    heal: str | None = None
    target_kind: str = "self"
    range_kind: str = "self"
    range_feet: int | None = None


class ResourceLine(_Line):
    key: str
    current: int
    maximum: int
    recharge: str


class InventoryLine(_Line):
    item: str
    name: str
    qty: int
    equipped_slot: str | None = None
    category: str = ""
    weight: float = 0.0
    value_gp: float = 0.0


class KeepsakeLine(_Line):
    """A story object the hero carries (M19.3): no value, cannot be sold or equipped."""

    name: str
    description: str = ""


class ConditionLine(_Line):
    name: str
    rounds_left: int | None = None


class DeathSaveLine(_Line):
    successes: int
    failures: int
    stable: bool
    dead: bool


class CharacterSheet(_Line):
    id: str
    name: str
    race: str
    subrace: str | None
    class_index: str
    subclass: str | None
    level: int
    background: str
    xp: int
    xp_next: int | None
    abilities: list[AbilityLine]
    skills: list[SkillLine]
    passive_perception: int
    proficiency_bonus: int
    ac: int
    hp: int
    temp_hp: int
    max_hp: int
    speed: int
    initiative_bonus: int
    initiative_die: str = "1d4"
    attacks: list[AttackLine]
    attacks_per_action: int
    spellcasting: SpellcastingBlock | None
    features: list[FeatureLine]
    feature_actions: list[FeatureActionLine] = []
    resources: list[ResourceLine]
    armor_proficiencies: list[str]
    weapon_proficiencies: list[str]
    tool_proficiencies: list[str]
    languages: list[str]
    resistances: list[DamageType]
    inventory: list[InventoryLine]
    keepsakes: list[KeepsakeLine] = []
    gold: int
    conditions: list[ConditionLine]
    death_saves: DeathSaveLine
    concentrating_on: str | None = None
