"""Typed dice values: parsed expressions and recorded rolls (pure data, no randomness here).

Public API:
- `DiceTerm(count, sides, keep_highest=None, keep_lowest=None)`: one `XdY` group, optionally
  `XdYkhN` / `XdYklN` (keep the N highest / lowest dice, e.g. "4d6kh3" for ability generation).
- `DiceExpr(terms, modifier)`: a sum of dice terms plus a flat integer modifier. `str(expr)` is the
  canonical text ("2d6+1d4+3", "1d4-1", "0"). Build one with `aidm.rules.dice.parse_dice`.
- `DieRoll(sides, value, kept)`: one physical die. Dropped dice stay visible with `kept=False`.
- `Roll(expression, dice, modifier, total)`: the result of rolling a `DiceExpr`.
  `total = sum(kept die values) + modifier`. The total is RAW arithmetic and may be negative
  (e.g. "1d4-3"); clamping damage to >= 0 is the job of the damage choke point (M1.4).
- `AdvState`: NORMAL / ADVANTAGE / DISADVANTAGE for a d20 test.
- `D20Roll(rolls, adv, natural, modifier, total, is_crit, is_fumble)`: a d20 test. `rolls` shows
  every d20 thrown (1 for NORMAL, 2 otherwise); `natural` is the chosen die.
- `RollKind` (M26.2): what a logged roll is for (attack, check, save, death_save, damage, heal,
  other); the dice show picks its staging from it.
- `RollPart(name, value)` (M26.2): one named piece of a d20 modifier ("DEX", "PROF",
  "EXPERTISE", "BONUS"); the parts of a check or save always sum to its modifier.

All models are frozen so they can be embedded in events and shared safely.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_DICE_COUNT = 100
MAX_DIE_SIDES = 100


class DiceTerm(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: int = Field(ge=1, le=MAX_DICE_COUNT)
    sides: int = Field(ge=2, le=MAX_DIE_SIDES)
    keep_highest: int | None = Field(default=None, ge=1)
    keep_lowest: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _check_keep(self) -> "DiceTerm":
        if self.keep_highest is not None and self.keep_lowest is not None:
            raise ValueError("a dice term keeps highest or lowest, not both")
        keep = self.keep_highest or self.keep_lowest
        if keep is not None and keep > self.count:
            raise ValueError(f"cannot keep {keep} of {self.count} dice")
        return self

    def __str__(self) -> str:
        text = f"{self.count}d{self.sides}"
        if self.keep_highest is not None:
            text += f"kh{self.keep_highest}"
        if self.keep_lowest is not None:
            text += f"kl{self.keep_lowest}"
        return text


class DiceExpr(BaseModel):
    model_config = ConfigDict(frozen=True)

    terms: tuple[DiceTerm, ...] = ()
    modifier: int = 0

    def __str__(self) -> str:
        text = "+".join(str(term) for term in self.terms)
        if not self.terms:
            return str(self.modifier)
        if self.modifier > 0:
            return f"{text}+{self.modifier}"
        if self.modifier < 0:
            return f"{text}{self.modifier}"
        return text


class DieRoll(BaseModel):
    model_config = ConfigDict(frozen=True)

    sides: int = Field(ge=2)
    value: int = Field(ge=1)
    kept: bool = True


class Roll(BaseModel):
    model_config = ConfigDict(frozen=True)

    expression: str
    dice: tuple[DieRoll, ...] = ()
    modifier: int = 0
    total: int


class AdvState(StrEnum):
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


class RollKind(StrEnum):
    ATTACK = "attack"
    CHECK = "check"
    SAVE = "save"
    DEATH_SAVE = "death_save"
    DAMAGE = "damage"
    HEAL = "heal"
    OTHER = "other"


class RollPart(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    value: int


class D20Roll(BaseModel):
    model_config = ConfigDict(frozen=True)

    rolls: tuple[int, ...] = Field(min_length=1, max_length=2)
    adv: AdvState = AdvState.NORMAL
    natural: int = Field(ge=1, le=20)
    modifier: int = 0
    total: int
    is_crit: bool = False
    is_fumble: bool = False
