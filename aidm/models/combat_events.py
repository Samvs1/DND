"""Combat command events (part of the `aidm.models.events.Event` union; same design rules apply).

Public API:
- `AttackRolled(attacker_id, target_id, attack, roll, bonus_rolls, target_ac, hit, crit)`: one
  resolved attack roll (log only: the damage events follow). `roll` is the d20 test with the
  attack bonus as modifier; `bonus_rolls` are added dice such as Bless; `target_ac` includes
  cover and AC buffs; `hit` / `crit` are final (natural 1 misses, a crit always hits).
- `CombatantMoved(creature_id, from_zone, to_zone, path, feet, reason)`: the combatant now
  stands in `to_zone` ("move", "jump", "shoved"); `path` lists the zones from start to goal and
  `feet` the movement it cost (0 when pushed). Applied by `aidm.session.encounter_apply`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.dice import D20Roll, Roll


class _CombatEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AttackRolled(_CombatEvent):
    type: Literal["attack_rolled"] = "attack_rolled"
    attacker_id: str
    target_id: str
    attack: str
    roll: D20Roll
    bonus_rolls: tuple[Roll, ...] = ()
    target_ac: int
    hit: bool
    crit: bool = False


class CombatantMoved(_CombatEvent):
    type: Literal["combatant_moved"] = "combatant_moved"
    creature_id: str
    from_zone: str
    to_zone: str
    path: tuple[str, ...] = ()
    feet: int = Field(default=0, ge=0)
    reason: str = "move"
