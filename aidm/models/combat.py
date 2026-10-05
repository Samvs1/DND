"""Attack options and the hit-chance preview (inputs and results of `aidm.rules` attacks).

Public API:
- `AttackEconomy`: what one use of an option costs: ATTACK (one attack of the Attack action;
  Extra Attack gives more per action), BONUS_ACTION (the off-hand attack), ACTION (Throw, a
  spell attack's cast pays for itself).
- `AttackProfile(key, name, attack_bonus, damage, damage_type, ranged, range_normal,
  range_long, context, economy)`: ONE attack option, the same shape for PC weapons, thrown
  objects, spell attacks and (M3.8) monster actions. `damage` is a dice expression with the
  modifiers already folded in ("1d8+3"; "" for a spell attack whose damage is DSL effects);
  `range_normal` / `range_long` are feet (melee: 5, or 10 with reach); `context` is the static
  `AttackContext` the feature hooks read (finesse, two-handed, off-hand, weapon die).
  `extra_damage` (M3.8) adds typed damage on a hit ("plus 3 (1d6) fire damage" on a monster
  bite); a crit doubles its dice too.
- `ExtraDamage(dice, damage_type)`: one such additional damage part.
- `HitChance(option, probability, crit_chance, adv, target_ac, attack_bonus, bonus_dice,
  in_range, long_range)`: the exact chance (0..1) an attack hits a target right now, computed
  over the d20 (and any bonus dice such as Bless), with the combined advantage state the hotbar
  shows. `probability` includes crits; out of range gives 0.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.damage import DamageType
from aidm.models.dice import AdvState
from aidm.models.features import AttackContext


class AttackEconomy(StrEnum):
    ATTACK = "attack"
    BONUS_ACTION = "bonus_action"
    ACTION = "action"


class ExtraDamage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dice: str = Field(min_length=1)
    damage_type: DamageType


class AttackProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    attack_bonus: int
    damage: str = ""
    damage_type: DamageType = DamageType.BLUDGEONING
    ranged: bool = False
    range_normal: int = Field(default=5, ge=0)
    range_long: int | None = Field(default=None, ge=0)
    context: AttackContext = AttackContext()
    economy: AttackEconomy = AttackEconomy.ATTACK
    extra_damage: tuple[ExtraDamage, ...] = ()


class HitChance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    option: str
    probability: float = Field(ge=0.0, le=1.0)
    crit_chance: float = Field(ge=0.0, le=1.0)
    adv: AdvState
    target_ac: int
    attack_bonus: int
    bonus_dice: tuple[str, ...] = ()
    in_range: bool = True
    long_range: bool = False
