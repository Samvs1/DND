"""Typed damage: every damage path carries a damage type (SPEC 7.1).

Public API:
- `DamageType`: the 13 SRD damage types. Values equal the SRD `damage-types` index
  ("acid", "bludgeoning", ...); a test verifies the set against data/srd/damage_types.json.
- `DamagePacket(amount, damage_type)`: one typed chunk of rolled damage, before resistances.
  `amount` is the raw roll total and may be negative ("1d4-3"); the choke point clamps it to 0.
  A hit dealing "1d8+3 slashing plus 2d6 fire" is two packets in ONE `resolve_damage` call.
- `DamagePart(damage_type, rolled, taken)`: one packet after immunity/resistance/vulnerability,
  as recorded in the `DamageTaken` event (`rolled` is the clamped input, `taken` the result).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DamageType(StrEnum):
    ACID = "acid"
    BLUDGEONING = "bludgeoning"
    COLD = "cold"
    FIRE = "fire"
    FORCE = "force"
    LIGHTNING = "lightning"
    NECROTIC = "necrotic"
    PIERCING = "piercing"
    POISON = "poison"
    PSYCHIC = "psychic"
    RADIANT = "radiant"
    SLASHING = "slashing"
    THUNDER = "thunder"


class DamagePacket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: int
    damage_type: DamageType


class DamagePart(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    damage_type: DamageType
    rolled: int = Field(ge=0)
    taken: int = Field(ge=0)
