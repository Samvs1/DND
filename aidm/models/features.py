"""Inputs and results of the feature hook interpreter (`aidm.rules.features`).

Public API:
- `AttackContext`: what the combat layer knows about one weapon attack when it asks for feature
  modifiers: `ranged`, `finesse`, `two_handed` (wielded in both hands), `offhand` (the light
  off-hand attack), `other_hand_weapon` (a second weapon is held), `adv` (the combined
  advantage state), `ally_adjacent` (a non-incapacitated ally of the attacker is next to the
  target), `target_wounded` (target below its HP maximum), `crit`, `weapon_die` (the weapon's
  damage die size, for riders that add weapon dice) and `used_once_per_turn` (feature ids whose
  once-per-turn rider already applied this turn).
- `DamageRider(feature, dice, flat, damage_type, once_per_turn, doubles_on_crit)`: extra damage a
  feature adds to a hit; `damage_type` None = the weapon's type; `doubles_on_crit` False for dice
  that are already the critical bonus (savage attacks).
- `ActionEconomy`: ACTION / BONUS_ACTION / EXTRA_ACTION (free: grants another action).
- `FeatureAction(feature, action, economy, resource, available, heal, name, command,
  target_kind, range_kind, range_feet)`: an action a feature offers (Cunning Action's dash,
  Second Wind, Action Surge, Breath Weapon); `available` is False while its resource is spent;
  `heal` is a resolved dice expression or None; `command` True when the `feature_action`
  command runs it (False: an existing command uses it, e.g. a bonus-action dash); the target
  fields say how the hotbar aims it (spell vocabulary: self / creature / area / point).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.damage import DamageType
from aidm.models.dice import AdvState


class AttackContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ranged: bool = False
    finesse: bool = False
    two_handed: bool = False
    offhand: bool = False
    other_hand_weapon: bool = False
    adv: AdvState = AdvState.NORMAL
    ally_adjacent: bool = False
    target_wounded: bool = False
    crit: bool = False
    weapon_die: int = Field(default=0, ge=0)
    used_once_per_turn: tuple[str, ...] = ()


class DamageRider(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: str
    dice: str | None = None
    flat: int = 0
    damage_type: DamageType | None = None
    once_per_turn: bool = False
    doubles_on_crit: bool = True


class ActionEconomy(StrEnum):
    ACTION = "action"
    BONUS_ACTION = "bonus_action"
    EXTRA_ACTION = "extra_action"


class FeatureAction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: str
    action: str
    economy: ActionEconomy
    resource: str | None = None
    available: bool = True
    heal: str | None = None
    name: str = ""
    command: bool = False
    target_kind: str = "self"
    range_kind: str = "self"
    range_feet: int | None = None
