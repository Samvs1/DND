"""Combat command events (part of the `aidm.models.events.Event` union; same design rules apply).

Public API:
- `AttackRolled(attacker_id, target_id, attack, roll, bonus_rolls, target_ac, hit, crit)`: one
  resolved attack roll (log only: the damage events follow). `roll` is the d20 test with the
  attack bonus as modifier; `bonus_rolls` are added dice such as Bless; `target_ac` includes
  cover and AC buffs; `hit` / `crit` are final (natural 1 misses, a crit always hits).
- `CombatantMoved(creature_id, from_zone, to_zone, path, feet, reason)`: the combatant now
  stands in `to_zone` ("move", "jump", "shoved"); `path` lists the zones from start to goal and
  `feet` the movement it cost (0 when pushed). Applied by `aidm.session.encounter_apply`.
- `SpellCast(caster_id, spell_id, cast_level, target_ids, target_zone)`: a spell was cast (log
  only; the slot, effects and concentration events follow). `cast_level` 0 for a cantrip.
- `ZoneSurfaceAdded(zone_id, surface)`: a surface now lies in the zone, replacing one of the same
  kind (its effects: `aidm.rules.surfaces`).
- `ZoneSurfaceRemoved(zone_id, kind, reason)`: the surface of that kind is gone from the zone.
- `ZoneSurfaceTicked(zone_id, kind, rounds_left)`: its remaining duration after a round start.
- `CreatureRevived(creature_id)`: a dead creature is alive again (still at 0 HP: the healing
  events that follow give it its hit points). Applied by the reducer (`dead` = False).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.dice import D20Roll, Roll
from aidm.models.zones import ZoneSurface


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


class SpellCast(_CombatEvent):
    type: Literal["spell_cast"] = "spell_cast"
    caster_id: str
    spell_id: str
    cast_level: int = Field(default=0, ge=0, le=9)
    target_ids: tuple[str, ...] = ()
    target_zone: str | None = None


class ZoneSurfaceAdded(_CombatEvent):
    type: Literal["zone_surface_added"] = "zone_surface_added"
    zone_id: str
    surface: ZoneSurface


class ZoneSurfaceRemoved(_CombatEvent):
    type: Literal["zone_surface_removed"] = "zone_surface_removed"
    zone_id: str
    kind: str
    reason: str = "expired"


class ZoneSurfaceTicked(_CombatEvent):
    type: Literal["zone_surface_ticked"] = "zone_surface_ticked"
    zone_id: str
    kind: str
    rounds_left: int = Field(ge=1)


class CreatureRevived(_CombatEvent):
    type: Literal["creature_revived"] = "creature_revived"
    creature_id: str
