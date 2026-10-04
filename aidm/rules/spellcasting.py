"""THE spell-slot model and spellcasting numbers (SPEC 7.2, 7.4, 8; one source of truth).

Slots are creature resources (`Creature.resources`, `aidm.rules.resources`), so there is one
storage and one recharge path: rests restore them by `RechargeKind` with every other resource.
- Standard slots: key `spell-slot-<n>` (spell level n = 1..9), LONG_REST.
- Pact slots: key `pact-slot-<n>` (all of the pact level n), SHORT_REST (and long rests).
Maximums come from the class data row for the level (`ClassLevelDef.slots`; a `pact` caster's
row lists its pact slots). Multiclassing is out of scope (single class per PC).

Public API:
- `SlotKind` (STANDARD / PACT), `SlotRef(kind, level)` with `.key`, `MAX_SPELL_LEVEL` (9),
  `SlotError(ValueError)` (no usable slot: the tool layer refuses the cast, nothing is spent).
- `slot_key(kind, level) -> str`; `parse_slot_key(key) -> SlotRef | None` (None = not a slot).
- `class_slot_maximums(class_def, level) -> dict[str, int]`: slot key -> maximum (non-zero only).
- `slot_resources(class_def, level) -> dict[str, Resource]`: full pools (character creation).
- `slot_maximum_events(creature, class_def, level) -> list[AnyEvent]`: re-derive the pools for a
  new level (level-up): spent slots stay spent (a pact pool that changes level carries its spent
  count), stale slot keys are removed (`ResourceRemoved`); other resources are untouched.
- `slot_pools(creature) -> list[tuple[SlotRef, Resource]]`: by level, standard before pact.
- `can_cast(creature, spell_level, slot_level=None) -> bool`; cantrips (level 0) always can.
- `choose_slot(creature, spell_level, slot_level=None) -> SlotRef`: the lowest usable slot at or
  above the spell level, or exactly `slot_level` (upcasting). A pact slot is always used at the
  pact level, so a request for another level never takes it. SlotError when none fits.
- `spend_slot(creature, spell_level, slot_level=None) -> list[AnyEvent]`: `[]` for a cantrip,
  else one `ResourceSet` spending the chosen slot (its key tells the cast level).
- `spellcasting_ability(class_def) -> Ability` (ValueError for a non-caster);
  `spell_save_dc(creature, class_def)` = 8 + proficiency bonus + ability modifier;
  `spell_attack_bonus(creature, class_def)` = proficiency bonus + ability modifier (SRD 5.1).
- `max_spell_level(class_def, level) -> int`: highest slot level the row has (0 = none).
- `cantrips_known_count(class_def, level)`; `spells_known_count(class_def, level) -> int`
  (known and pact casters; 0 for others); `prepared_spell_limit(class_def, level, abilities)`:
  prepared casters prepare ability modifier + level spells, at least 1 (SRD 5.1 Cleric/Wizard);
  0 for known/pact casters and non-casters. Wizards prepare from their spellbook (validated by
  `aidm.rules.creation`).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from aidm.data.class_defs import ClassDef
from aidm.models.abilities import Ability
from aidm.models.events import AnyEvent, ResourceRemoved, ResourceSet
from aidm.models.state import Creature, RechargeKind, Resource
from aidm.rules.abilities import ability_modifier

MAX_SPELL_LEVEL = 9
SPELL_DC_BASE = 8


class SlotKind(StrEnum):
    STANDARD = "spell-slot"
    PACT = "pact-slot"


_RECHARGE: dict[SlotKind, RechargeKind] = {
    SlotKind.STANDARD: RechargeKind.LONG_REST,
    SlotKind.PACT: RechargeKind.SHORT_REST,
}


_KIND_VALUES = frozenset(kind.value for kind in SlotKind)


class SlotError(ValueError):
    """No slot can pay for this spell (unknown level, none left, or a level the caster lacks)."""


@dataclass(frozen=True, order=True)
class SlotRef:
    level: int
    kind: SlotKind

    @property
    def key(self) -> str:
        return slot_key(self.kind, self.level)


def slot_key(kind: SlotKind, level: int) -> str:
    if not 1 <= level <= MAX_SPELL_LEVEL:
        raise ValueError(f"slot level {level} outside 1..{MAX_SPELL_LEVEL}")
    return f"{kind.value}-{level}"


def parse_slot_key(key: str) -> SlotRef | None:
    prefix, _, number = key.rpartition("-")
    if prefix not in _KIND_VALUES or not number.isdigit():
        return None
    level = int(number)
    if not 1 <= level <= MAX_SPELL_LEVEL:
        return None
    return SlotRef(level=level, kind=SlotKind(prefix))


def _kind_of(class_def: ClassDef) -> SlotKind | None:
    casting = class_def.spellcasting
    if casting is None:
        return None
    return SlotKind.PACT if casting.kind == "pact" else SlotKind.STANDARD


def _class_slots(class_def: ClassDef, level: int) -> list[tuple[SlotRef, int]]:
    kind = _kind_of(class_def)
    if kind is None:
        return []
    row = class_def.level(level)
    return [(SlotRef(level=i + 1, kind=kind), n) for i, n in enumerate(row.slots) if n > 0]


def class_slot_maximums(class_def: ClassDef, level: int) -> dict[str, int]:
    return {ref.key: n for ref, n in _class_slots(class_def, level)}


def _full_pool(ref: SlotRef, maximum: int) -> Resource:
    return Resource(current=maximum, maximum=maximum, recharge=_RECHARGE[ref.kind])


def slot_resources(class_def: ClassDef, level: int) -> dict[str, Resource]:
    return {ref.key: _full_pool(ref, n) for ref, n in _class_slots(class_def, level)}


def slot_pools(creature: Creature) -> list[tuple[SlotRef, Resource]]:
    pools: list[tuple[SlotRef, Resource]] = []
    for key, resource in creature.resources.items():
        ref = parse_slot_key(key)
        if ref is not None:
            pools.append((ref, resource))
    pools.sort(key=lambda pair: (pair[0].level, pair[0].kind is SlotKind.PACT))
    return pools


def _pact_spent(creature: Creature) -> int:
    pools = slot_pools(creature)
    return sum(r.maximum - r.current for ref, r in pools if ref.kind is SlotKind.PACT)


def slot_maximum_events(creature: Creature, class_def: ClassDef, level: int) -> list[AnyEvent]:
    fresh = _class_slots(class_def, level)
    keep = {ref.key for ref, _ in fresh}
    events: list[AnyEvent] = [
        ResourceRemoved(creature_id=creature.id, key=ref.key)
        for ref, _ in slot_pools(creature)
        if ref.key not in keep
    ]
    pact_spent = _pact_spent(creature)
    for ref, maximum in fresh:
        old = creature.resources.get(ref.key)
        if old is not None:
            spent = old.maximum - old.current
        else:
            spent = pact_spent if ref.kind is SlotKind.PACT else 0
        pool = _full_pool(ref, maximum)
        updated = pool.model_copy(update={"current": max(0, maximum - spent)})
        if updated != old:
            events.append(ResourceSet(creature_id=creature.id, key=ref.key, resource=updated))
    return events


def _check_spell_level(spell_level: int) -> None:
    if not 0 <= spell_level <= MAX_SPELL_LEVEL:
        raise SlotError(f"spell level {spell_level} outside 0..{MAX_SPELL_LEVEL}")


def choose_slot(creature: Creature, spell_level: int, slot_level: int | None = None) -> SlotRef:
    _check_spell_level(spell_level)
    if spell_level == 0:
        raise SlotError("cantrips use no slot")
    if slot_level is not None and slot_level < spell_level:
        raise SlotError(f"a level {spell_level} spell cannot use a level {slot_level} slot")
    for ref, resource in slot_pools(creature):
        fits = ref.level >= spell_level if slot_level is None else ref.level == slot_level
        if fits and resource.current > 0:
            return ref
    wanted = f"level {slot_level}" if slot_level is not None else f"level {spell_level}+"
    raise SlotError(f"{creature.id!r} has no {wanted} slot left")


def can_cast(creature: Creature, spell_level: int, slot_level: int | None = None) -> bool:
    if spell_level == 0 and slot_level is None:
        return True
    try:
        choose_slot(creature, spell_level, slot_level)
    except SlotError:
        return False
    return True


def spend_slot(
    creature: Creature, spell_level: int, slot_level: int | None = None
) -> list[AnyEvent]:
    _check_spell_level(spell_level)
    if spell_level == 0 and slot_level is None:
        return []
    ref = choose_slot(creature, spell_level, slot_level)
    resource = creature.resources[ref.key]
    spent = resource.model_copy(update={"current": resource.current - 1})
    return [ResourceSet(creature_id=creature.id, key=ref.key, resource=spent)]


def spellcasting_ability(class_def: ClassDef) -> Ability:
    if class_def.spellcasting is None:
        raise ValueError(f"{class_def.index} is not a spellcaster")
    return Ability(class_def.spellcasting.ability)


def _casting_mod(creature: Creature, class_def: ClassDef) -> int:
    return ability_modifier(creature.abilities[spellcasting_ability(class_def)])


def spell_save_dc(creature: Creature, class_def: ClassDef) -> int:
    return SPELL_DC_BASE + creature.proficiency_bonus + _casting_mod(creature, class_def)


def spell_attack_bonus(creature: Creature, class_def: ClassDef) -> int:
    return creature.proficiency_bonus + _casting_mod(creature, class_def)


def max_spell_level(class_def: ClassDef, level: int) -> int:
    slots = class_def.level(level).slots
    return max((i + 1 for i, n in enumerate(slots) if n > 0), default=0)


def cantrips_known_count(class_def: ClassDef, level: int) -> int:
    return class_def.level(level).cantrips_known


def spells_known_count(class_def: ClassDef, level: int) -> int:
    return class_def.level(level).spells_known or 0


def prepared_spell_limit(class_def: ClassDef, level: int, abilities: Mapping[Ability, int]) -> int:
    casting = class_def.spellcasting
    if casting is None or casting.kind != "prepared" or level < casting.first_level:
        return 0
    return max(1, ability_modifier(abilities[Ability(casting.ability)]) + level)
