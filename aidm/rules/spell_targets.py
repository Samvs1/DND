"""Spell casting checks before any event: caster numbers, the slot, and the targets in range.

All functions raise `CommandRefused` for invalid input, so a refused cast consumes nothing.

Public API:
- `CasterNumbers(save_dc, attack_bonus, modifier, resource)`; `caster_numbers(creature, spell_id,
  regs) -> CasterNumbers`: the spell must be on the caster's sheet and prepared (cantrips,
  known spells, prepared or always-prepared domain spells, racial spells); numbers come from
  the ONE sheet builder (`rules.sheet_spells.spellcasting_block`). `resource` names the
  per-rest resource of an innate (racial) spell.
- `cast_slot(creature, spell, slot_level, resource) -> tuple[int, list[AnyEvent]]`: the cast
  level and the spend events: cantrips are free (level 0, no slot allowed); an innate spell
  with its resource left spends that; a monster's at-will innate spell (`resource` AT_WILL)
  costs nothing; otherwise `rules.spellcasting.choose_slot/spend_slot`
  (the lowest usable slot, or exactly `slot_level` to upcast).
- `instance_count(spell, cast_level, char_level) -> int`: how many target instances the
  targeting block allows at this cast (count + count_per_slot per level above, or the cantrip
  table by character level).
- `spell_band(spell) -> RangeBand`: self and touch = the same zone, feet = its range band.
- `area_zones(zone_map, start, spell) -> tuple[str, ...]`: the zones an area or point spell cast
  from `start` can be aimed at: in its range band; a self-ranged area covers the caster's zone,
  and an aimed self `shape` (M29.7d: cone, line, cube) also reaches a neighbouring zone whose
  edge is no longer than the shape (Burning Hands 15 ft over a 15-ft edge, Fear 30 ft over 25).
- `needs_battlefield(spell) -> bool`: the spell cannot resolve outside a fight (below).
- `area_creatures(state, zone_id, area, exclude) -> tuple[str, ...]`: living, present
  combatants in the zone (and its neighbours for "zone_and_adjacent").
- `SpellTargets(instances, zone, chosen)`; `resolve_targets(state, caster_id, spell, cast_level,
  char_level, target_ids, target_zone) -> SpellTargets`: validated targets. Outside an active
  fight there are no zones: range is not checked, and spells with an attack roll, a save or
  damage (hostile acts start a fight first), area and point spells are refused. A "point" spell
  picks a zone in range and its only instance is the caster. Dead creatures are refused unless
  the targeting asks for dead targets (then only dead ones); creatures outside the targeting's
  `creature_types` are refused (an area keeps only those types: Turn Undead), and so are those
  the targeting excludes (`spell_can_affect`, M29.9a: Sleep leaves out undead and the
  charm-immune, so its pool is never spent on them); `order`
  "hp_ascending" sorts the instances by current HP (stable, ties keep their order).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from aidm.data.character_data import CharacterRegistries
from aidm.data.spell_defs import (
    AreaKey,
    AttackRollEffect,
    DamageEffect,
    Effect,
    SaveEffect,
    SpellDef,
    Targeting,
)
from aidm.models.commands import RefusalCode
from aidm.models.encounter import Encounter, EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.sheet import SpellLine
from aidm.models.state import Creature, GameState
from aidm.models.zones import RangeBand, ZoneMap
from aidm.rules.abilities import ability_modifier
from aidm.rules.command_checks import CommandRefused
from aidm.rules.features import dice_at_level
from aidm.rules.monster_keys import AT_WILL
from aidm.rules.monster_stats import creature_type_of
from aidm.rules.resources import resource_left, spend_resource
from aidm.rules.sheet_spells import spellcasting_block
from aidm.rules.spellcasting import SlotError, choose_slot, spend_slot
from aidm.rules.zones import (
    MELEE_BAND,
    edge_feet,
    range_band,
    zone_neighbors,
    zone_range_check,
)


@dataclass(frozen=True)
class CasterNumbers:
    save_dc: int
    attack_bonus: int
    modifier: int
    resource: str | None = None


@dataclass(frozen=True)
class SpellTargets:
    instances: tuple[str, ...]
    zone: str | None = None
    chosen: tuple[str, ...] = ()


def _refuse(code: RefusalCode, reason: str) -> CommandRefused:
    return CommandRefused(code, reason)


def caster_numbers(creature: Creature, spell_id: str, regs: CharacterRegistries) -> CasterNumbers:
    block = spellcasting_block(creature, regs)
    if block is None:
        raise _refuse(RefusalCode.NOT_A_CASTER, "You cannot cast spells.")
    lines: list[SpellLine] = [*block.cantrips, *(s for g in block.levels for s in g.spells)]
    line = next((s for s in lines if s.index == spell_id), None)
    if line is None or not line.prepared:
        raise _refuse(RefusalCode.SPELL_NOT_READY, "You do not have that spell ready.")
    return CasterNumbers(
        save_dc=block.save_dc,
        attack_bonus=block.attack_bonus,
        modifier=ability_modifier(creature.abilities[block.ability]),
        resource=line.resource,
    )


def cast_slot(
    creature: Creature, spell: SpellDef, slot_level: int | None, resource: str | None
) -> tuple[int, list[AnyEvent]]:
    if spell.level == 0:
        if slot_level is not None:
            raise _refuse(RefusalCode.NO_SLOT, "Cantrips do not use spell slots.")
        return 0, []
    if resource == AT_WILL and slot_level is None:
        return spell.level, []
    if resource and slot_level is None and resource_left(creature, resource) > 0:
        return spell.level, spend_resource(creature, resource)
    try:
        ref = choose_slot(creature, spell.level, slot_level)
        return ref.level, spend_slot(creature, spell.level, slot_level)
    except SlotError:
        raise _refuse(RefusalCode.NO_SLOT, "You have no spell slot left for that.") from None


def instance_count(spell: SpellDef, cast_level: int, char_level: int) -> int:
    targeting = spell.targeting
    if targeting.count_by_character_level:
        table = {lvl: str(n) for lvl, n in targeting.count_by_character_level.items()}
        return int(dice_at_level(table, char_level) or targeting.count)
    return targeting.count + targeting.count_per_slot * max(0, cast_level - spell.level)


def spell_band(spell: SpellDef) -> RangeBand:
    if spell.range.kind == "feet" and spell.range.feet is not None:
        return range_band(spell.range.feet)
    return MELEE_BAND


def area_zones(zone_map: ZoneMap, start: str, spell: SpellDef) -> tuple[str, ...]:
    if spell.range.kind != "self":
        band = spell_band(spell)
        return tuple(
            z.id for z in zone_map.zones if zone_range_check(zone_map, start, z.id, band).in_range
        )
    shape = spell.targeting.shape
    if shape is None:
        return (start,)
    near = [z for z, _ in zone_neighbors(zone_map, start)]
    return (start, *(z for z in near if (edge_feet(zone_map, start, z) or 0) <= shape.feet))


def _active(state: GameState) -> Encounter | None:
    enc = state.encounter
    return enc if enc is not None and enc.status is EncounterStatus.ACTIVE else None


def area_creatures(
    state: GameState, zone_id: str, area: AreaKey, exclude: Collection[str]
) -> tuple[str, ...]:
    enc = _active(state)
    if enc is None:
        return ()
    zones = {zone_id}
    if area == "zone_and_adjacent":
        zones |= {z for z, _ in zone_neighbors(enc.zone_map, zone_id)}
    found: list[str] = []
    for cid, combatant in enc.combatants.items():
        creature = state.creatures.get(cid)
        if creature is None or creature.dead or combatant.withdrawn is not None:
            continue
        if combatant.zone_id in zones and cid not in exclude:
            found.append(cid)
    return tuple(found)


def _needs_fight(effects: Sequence[Effect]) -> bool:
    return any(isinstance(e, (AttackRollEffect, SaveEffect, DamageEffect)) for e in effects)


def needs_battlefield(spell: SpellDef) -> bool:
    """Outside a fight this spell is refused by `resolve_targets` (an attack, a save, damage, an
    area or a point: M27.7 reads it as an attack when aimed at someone)."""
    return spell.targeting.kind in ("area", "point") or _needs_fight(spell.effects)


def spell_can_affect(creature: Creature, targeting: Targeting) -> bool:
    """The targeting's creature types admit `creature` and none of its exclusions apply."""
    kind = creature_type_of(creature)
    if targeting.creature_types and kind not in targeting.creature_types:
        return False
    if kind in targeting.exclude_creature_types:
        return False
    return not set(targeting.exclude_condition_immune) & set(creature.condition_immunities)


def _check_creature(
    state: GameState, enc: Encounter | None, caster_id: str, cid: str, spell: SpellDef
) -> None:
    creature = state.creatures.get(cid)
    if creature is None:
        raise _refuse(RefusalCode.UNKNOWN_TARGET, "There is no one like that here.")
    if creature.dead and not spell.targeting.dead:
        raise _refuse(RefusalCode.INVALID_TARGET, f"It is too late for {creature.name}.")
    if spell.targeting.dead and not creature.dead:
        raise _refuse(RefusalCode.INVALID_TARGET, f"{creature.name} is not dead.")
    if not spell_can_affect(creature, spell.targeting):
        raise _refuse(RefusalCode.INVALID_TARGET, f"That spell cannot affect {creature.name}.")
    band = spell_band(spell)
    if enc is None:
        return
    combatant = enc.combatants.get(cid)
    if combatant is None or combatant.withdrawn is not None:
        raise _refuse(RefusalCode.INVALID_TARGET, f"{creature.name} is not in this fight.")
    start = enc.combatant(caster_id).zone_id
    if not zone_range_check(enc.zone_map, start, combatant.zone_id, band).in_range:
        raise _refuse(RefusalCode.OUT_OF_RANGE, f"{creature.name} is out of range.")


def _area_targets(
    state: GameState,
    enc: Encounter | None,
    caster_id: str,
    spell: SpellDef,
    target_zone: str | None,
) -> SpellTargets:
    if enc is None:
        raise _refuse(RefusalCode.NOT_IN_COMBAT, "That spell needs a battlefield.")
    start = enc.combatant(caster_id).zone_id
    aimed = spell.range.kind != "self" or spell.targeting.shape is not None
    zone = (target_zone or (start if spell.range.kind == "self" else None)) if aimed else start
    if zone is None or not enc.zone_map.has_zone(zone):
        raise _refuse(RefusalCode.UNKNOWN_ZONE, "Choose an area for that spell.")
    if zone not in area_zones(enc.zone_map, start, spell):
        raise _refuse(RefusalCode.OUT_OF_RANGE, _out_of_reach(enc.zone_map, start, zone, spell))
    if spell.targeting.kind == "point":
        return SpellTargets(instances=(caster_id,), zone=zone, chosen=(caster_id,))
    area = spell.targeting.area or "zone"
    found = area_creatures(state, zone, area, {caster_id})
    found = tuple(c for c in found if spell_can_affect(state.creatures[c], spell.targeting))
    return SpellTargets(instances=found, zone=zone)


def _out_of_reach(zone_map: ZoneMap, start: str, zone: str, spell: SpellDef) -> str:
    shape = spell.targeting.shape
    if shape is None:
        return "That area is out of range."
    name = zone_map.zone(zone).name
    feet = edge_feet(zone_map, start, zone)
    if feet is None:
        return f"The {shape.feet}-ft {shape.kind} cannot reach {name} from here."
    return f"The {shape.feet}-ft {shape.kind} does not reach {name}, {feet} ft away."


def _picked(spell: SpellDef, target_ids: Sequence[str], allowed: int) -> tuple[str, ...]:
    if not target_ids:
        raise _refuse(RefusalCode.BAD_TARGETS, "Choose a target.")
    if len(target_ids) > allowed:
        raise _refuse(RefusalCode.BAD_TARGETS, f"Choose at most {allowed} target(s).")
    if spell.targeting.repeat:
        return tuple(target_ids[i % len(target_ids)] for i in range(allowed))
    if len(set(target_ids)) != len(target_ids):
        raise _refuse(RefusalCode.BAD_TARGETS, "Each creature can only be chosen once.")
    return tuple(target_ids)


def resolve_targets(
    state: GameState,
    caster_id: str,
    spell: SpellDef,
    cast_level: int,
    char_level: int,
    target_ids: Sequence[str],
    target_zone: str | None,
) -> SpellTargets:
    enc = _active(state)
    if enc is not None and caster_id not in enc.combatants:
        enc = None
    kind = spell.targeting.kind
    if enc is None and _needs_fight(spell.effects):
        raise _refuse(RefusalCode.NOT_IN_COMBAT, "That spell needs a battlefield.")
    if kind in ("area", "point"):
        return _ordered(state, spell, _area_targets(state, enc, caster_id, spell, target_zone))
    if kind == "self":
        if any(t != caster_id for t in target_ids):
            raise _refuse(RefusalCode.BAD_TARGETS, "That spell only affects you.")
        return SpellTargets(instances=(caster_id,), chosen=(caster_id,))
    allowed = 1 if kind == "creature" else instance_count(spell, cast_level, char_level)
    instances = _picked(spell, target_ids, allowed)
    for cid in dict.fromkeys(instances):
        _check_creature(state, enc, caster_id, cid, spell)
    return _ordered(state, spell, SpellTargets(instances=instances, chosen=tuple(target_ids)))


def _ordered(state: GameState, spell: SpellDef, targets: SpellTargets) -> SpellTargets:
    if spell.targeting.order != "hp_ascending":
        return targets
    ranked = sorted(targets.instances, key=lambda cid: state.creatures[cid].hp)
    return SpellTargets(instances=tuple(ranked), zone=targets.zone, chosen=targets.chosen)
