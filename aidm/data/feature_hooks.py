"""Feature hook schema: the typed effects of a class, subclass or race feature (SPEC 7.4).

Every feature in data/bg3/features.json lists hooks; ONE interpreter (`aidm.rules.features`
for combat-time queries, `aidm.rules.feature_build` for build and level-up) reads them. Adding a
feature is a JSON change, never a per-feature branch in code.

Every hook has `min_level` (the character level it starts working at, default 1) and a `kind`:
- `damage_rider`: extra damage on a weapon hit: `dice_by_level` (character level -> dice, the
  highest key at or below the level wins), `weapon_dice` (extra weapon damage dice, savage
  attacks), `flat`, `damage_type` (None = the weapon's), `weapon` filter, `trigger`
  (always / advantage_or_ally / target_wounded / crit) and `once_per_turn`.
- `sneak_attack`: a rider preset: `dice_by_level`, finesse or ranged, advantage or an ally
  next to the target, once per turn (SRD Sneak Attack).
- `bonus_action`: `actions` the feature lets the creature take as a bonus action, optional
  `resource` spent per use and `heal` (dice; "LEVEL" is replaced by the character level).
- `extra_action`: `actions` extra actions on the turn, paid with `resource` (Action Surge).
- `active_ability` (M7.5b): an activated ability run through THE spell effect interpreter as a
  pseudo spell: `name`, `activation` (action / bonus_action), optional `resource` spent per
  use, `range`/`targeting`/`effects` exactly as in a spell file (aidm.data.spell_defs), the save
  DC 8 + proficiency + the `dc_ability` modifier, `magical` (counts as magic for save
  advantages). Breath Weapon (per draconic ancestry), Turn Undead.
- `resource`: a pool `key` with `uses` that recharges on a `short_rest` or `long_rest`.
- `fighting_style`: `attack_bonus`, `damage_bonus`, `ac_bonus` (only while wearing body armor
  when `requires_armor`), `reroll_damage_below` (reroll damage dice under this value once),
  `offhand_ability_damage` (the off-hand attack adds the ability modifier), all gated by `weapon`.
- `expertise`: choose `choose` proficient skills; their proficiency bonus doubles.
- `resistance`: damage types resisted. `advantage_on`: advantage on saves against any of the
  `saves_against` tags (a condition key, a damage type or "magic"), limited to `abilities`.
- `attack_advantage` (M3.8, monster traits): advantage on attack rolls while `trigger` holds
  ("ally_adjacent": a standing, non-incapacitated ally shares the target's zone; Pack Tactics).
- `extra_attack`: `attacks` more attacks per Attack action (the highest one counts).
- `toggle`: an on/off state (rage-style): activating spends `resource`, applies `condition` to
  the creature (source id = `key`) and turns on `while_active` hooks (attack-time kinds only).
- `stat_bonus`: `hp_per_level` (maximum HP per character level) and `speed`.
- `proficiency`: `armor`, `weapons`, `tools`, `skills` granted (SRD proficiency/skill indexes).
- `improved_critical`: attacks crit on a natural `crit_on` or higher.
- `spell_grant`: `spells` the feature grants (known, always prepared, or added to the class list
  as `expanded`), optionally only for one `subclass`, cast with a `resource` at `cast_level`;
  `ability` is the casting ability for them (and for picked race cantrips when
  `covers_race_cantrips`).
- `darkvision`: range in feet. `healing_bonus`: healing spells of `min_spell_level`+ heal
  `base + per_spell_level * spell level` more. `kill_temp_hp`: temporary HP equal to the
  `ability` modifier (+ level when `add_level`), at least `minimum`, on dropping a foe to 0.
- `slot_recovery`: spend `resource` on a short rest to regain spell slots whose levels add up
  to half the character level (rounded up, `level_divisor`), none above `max_slot_level`.
- `scroll_copy`: copy spell scrolls into a spellbook for `gold_per_level` gold per spell level;
  an entry with a `school` changes that school's cost to `cost_percent`.
- `reroll_ones`: a natural 1 on the listed d20 `tests` is rerolled once.
- `drop_to_one` (M29.9a): damage that would drop the creature from above 0 to 0 HP without
  killing it outright leaves it at 1 HP instead, spending one use of `resource` (SRD 5.1
  Half-Orc Relentless Endurance; `aidm.rules.hp_floor`, read at the damage choke point).
- `unsupported`: the mechanic is not modelled yet; `reason` is listed in docs/RULES_DECISIONS.md.

Public API: the hook classes, `FeatureHook` (discriminated union), `ActiveEffectHook` (the kinds
a toggle may switch on), `GrantedSpell`, and the literal key types.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.data.ac_formulas import AbilityKey
from aidm.data.condition_defs import DamageKey
from aidm.data.spell_defs import Effect, SpellRange, Targeting

type WeaponNeed = Literal[
    "any", "melee", "ranged", "finesse_or_ranged", "melee_one_handed", "melee_two_handed", "offhand"
]
type RiderTrigger = Literal["always", "advantage_or_ally", "target_wounded", "crit"]
type RechargeKey = Literal["short_rest", "long_rest"]
type TestKey = Literal["attack", "check", "save"]
type GrantMode = Literal["known", "always_prepared", "expanded"]
type ActivationKey = Literal["action", "bonus_action", "free"]


class _Hook(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min_level: int = Field(default=1, ge=1, le=20)


class DamageRiderHook(_Hook):
    kind: Literal["damage_rider"] = "damage_rider"
    dice_by_level: dict[int, str] = Field(default_factory=dict[int, str])
    weapon_dice: int = Field(default=0, ge=0)
    flat: int = 0
    damage_type: DamageKey | None = None
    weapon: WeaponNeed = "any"
    trigger: RiderTrigger = "always"
    once_per_turn: bool = False


class SneakAttackHook(_Hook):
    kind: Literal["sneak_attack"] = "sneak_attack"
    dice_by_level: dict[int, str] = Field(min_length=1)


class BonusActionHook(_Hook):
    kind: Literal["bonus_action"] = "bonus_action"
    actions: tuple[str, ...] = Field(min_length=1)
    resource: str | None = None
    heal: str | None = None


class ExtraActionHook(_Hook):
    kind: Literal["extra_action"] = "extra_action"
    actions: int = Field(default=1, ge=1)
    resource: str = Field(min_length=1)


class ActiveAbilityHook(_Hook):
    kind: Literal["active_ability"] = "active_ability"
    name: str = Field(min_length=1)
    activation: Literal["action", "bonus_action"] = "action"
    resource: str | None = None
    dc_ability: AbilityKey
    magical: bool = False
    range: SpellRange
    targeting: Targeting
    effects: tuple[Effect, ...] = Field(min_length=1)


class ResourceHook(_Hook):
    kind: Literal["resource"] = "resource"
    key: str = Field(min_length=1)
    uses: int = Field(ge=1)
    recharge: RechargeKey


class FightingStyleHook(_Hook):
    kind: Literal["fighting_style"] = "fighting_style"
    attack_bonus: int = 0
    damage_bonus: int = 0
    ac_bonus: int = 0
    requires_armor: bool = False
    reroll_damage_below: int = Field(default=0, ge=0)
    offhand_ability_damage: bool = False
    weapon: WeaponNeed = "any"


class ExpertiseHook(_Hook):
    kind: Literal["expertise"] = "expertise"
    choose: int = Field(ge=1)


class ResistanceHook(_Hook):
    kind: Literal["resistance"] = "resistance"
    damage_types: tuple[DamageKey, ...] = Field(min_length=1)


class AdvantageOnHook(_Hook):
    kind: Literal["advantage_on"] = "advantage_on"
    saves_against: tuple[str, ...] = Field(min_length=1)
    abilities: tuple[AbilityKey, ...] = ()


class AttackAdvantageHook(_Hook):
    kind: Literal["attack_advantage"] = "attack_advantage"
    trigger: Literal["ally_adjacent"] = "ally_adjacent"


class ExtraAttackHook(_Hook):
    kind: Literal["extra_attack"] = "extra_attack"
    attacks: int = Field(default=1, ge=1)


class ImprovedCriticalHook(_Hook):
    kind: Literal["improved_critical"] = "improved_critical"
    crit_on: int = Field(ge=2, le=20)


ActiveEffectHook = Annotated[
    DamageRiderHook | FightingStyleHook | AdvantageOnHook | ExtraAttackHook | ImprovedCriticalHook,
    Field(discriminator="kind"),
]


class ToggleHook(_Hook):
    kind: Literal["toggle"] = "toggle"
    key: str = Field(min_length=1)
    condition: str = Field(min_length=1)
    activation: ActivationKey = "bonus_action"
    resource: str | None = None
    while_active: tuple[ActiveEffectHook, ...] = ()


class StatBonusHook(_Hook):
    kind: Literal["stat_bonus"] = "stat_bonus"
    hp_per_level: int = 0
    speed: int = 0


class ProficiencyHook(_Hook):
    kind: Literal["proficiency"] = "proficiency"
    armor: tuple[str, ...] = ()
    weapons: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()


class GrantedSpell(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    spell: str = Field(min_length=1)
    min_level: int = Field(default=1, ge=1, le=20)
    mode: GrantMode = "known"
    subclass: str | None = None
    resource: str | None = None
    cast_level: int | None = Field(default=None, ge=1, le=9)


class SpellGrantHook(_Hook):
    kind: Literal["spell_grant"] = "spell_grant"
    spells: tuple[GrantedSpell, ...] = ()
    ability: AbilityKey | None = None
    covers_race_cantrips: bool = False


class DarkvisionHook(_Hook):
    kind: Literal["darkvision"] = "darkvision"
    range: int = Field(ge=0)


class HealingBonusHook(_Hook):
    kind: Literal["healing_bonus"] = "healing_bonus"
    base: int = 0
    per_spell_level: int = 0
    min_spell_level: int = Field(default=1, ge=0)


class KillTempHpHook(_Hook):
    kind: Literal["kill_temp_hp"] = "kill_temp_hp"
    ability: AbilityKey
    add_level: bool = True
    minimum: int = Field(default=1, ge=0)


class SlotRecoveryHook(_Hook):
    kind: Literal["slot_recovery"] = "slot_recovery"
    resource: str = Field(min_length=1)
    level_divisor: int = Field(default=2, ge=1)
    max_slot_level: int = Field(default=5, ge=1, le=9)


class ScrollCopyHook(_Hook):
    kind: Literal["scroll_copy"] = "scroll_copy"
    gold_per_level: int = Field(default=0, ge=0)
    school: str | None = None
    cost_percent: int = Field(default=100, ge=0, le=100)


class RerollOnesHook(_Hook):
    kind: Literal["reroll_ones"] = "reroll_ones"
    tests: tuple[TestKey, ...] = Field(min_length=1)


class DropToOneHook(_Hook):
    kind: Literal["drop_to_one"] = "drop_to_one"
    resource: str = Field(min_length=1)


class UnsupportedHook(_Hook):
    kind: Literal["unsupported"] = "unsupported"
    reason: str = Field(min_length=1)


FeatureHook = Annotated[
    DamageRiderHook
    | SneakAttackHook
    | BonusActionHook
    | ExtraActionHook
    | ActiveAbilityHook
    | ResourceHook
    | FightingStyleHook
    | ExpertiseHook
    | ResistanceHook
    | AdvantageOnHook
    | AttackAdvantageHook
    | ExtraAttackHook
    | ToggleHook
    | StatBonusHook
    | ProficiencyHook
    | ImprovedCriticalHook
    | SpellGrantHook
    | DarkvisionHook
    | HealingBonusHook
    | KillTempHpHook
    | SlotRecoveryHook
    | ScrollCopyHook
    | RerollOnesHook
    | DropToOneHook
    | UnsupportedHook,
    Field(discriminator="kind"),
]
