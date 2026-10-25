"""Equip, unequip and drop for heroes (SPEC 6.2 equipment pre-checks; M6.2).

Slots follow `aidm.models.character.Equipped`: body armour, shield, main hand, off hand, ranged.
Equipping a two-handed weapon frees the off hand and the shield; a weapon that is not light
frees the off hand (SRD two-weapon fighting needs light weapons); a shield frees the off hand
and a two-handed main weapon. The armour class moves by the DIFFERENCE between the old and the
new gear (armour formula + shield + armour-dependent fighting styles), the same delta rule
level-up uses, so feature bonuses already in `Creature.ac` are kept. Dropping puts ONE item on
the ground at the current place (`ItemPlaced`), unequipping the last equipped copy first (M27.7:
only ONE slot is freed, the off hand first, so dropping one of two wielded daggers keeps the
other in hand; `release_events` is that step, also used by a throw).
Taking (M19.3) is the reverse: a visible item lying at the current place leaves it
(`ItemRemoved`) and joins the hero: a catalogue item into the inventory, anything else (a story
object with no catalogue entry) as a keepsake; a quest item keeps its `quest_id` (M23.3).
M36.4 (round 6 Y12): `qty` takes that many units of a stack (`ItemRemoved.qty`, the rest stays
where it lies); none, or more than lie there, takes the whole stack.

M30.0b T9: `draw_events` is the free object interaction of an attack (SRD 5.1 "Other Activity
on Your Turn": draw a weapon as part of the attack; BG3 swaps weapons freely): a carried weapon
goes to its hand as with equip, mid-fight too; one already in hand needs nothing.

Public API: `EquipRefusal`, `EquipRefused`, `equip_events(creature, item, regs)`,
`draw_events(creature, item, regs)`,
`unequip_events(creature, item, regs)`, `release_events(creature, item, regs, qty=1)`,
`drop_events(state, creature, item, regs)`,
`take_events(state, creature, item_id, qty=None)`.
"""

from enum import StrEnum

from aidm.data.character_data import CharacterRegistries
from aidm.data.srd_equipment import SrdEquipment
from aidm.models.character import Equipped, Keepsake
from aidm.models.events import AnyEvent, InventoryChanged
from aidm.models.state import Creature, GameState
from aidm.models.world import WorldItem
from aidm.models.world_events import EquipmentChanged, ItemPlaced, ItemRemoved, KeepsakeGained
from aidm.rules.defense import armor_class
from aidm.rules.features import feature_ac_bonus
from aidm.rules.item_grants import carried_qty
from aidm.rules.lore import lore_events

SHIELD = "Shield"
_SLOTS = ("armor", "shield", "main_hand", "off_hand", "ranged")


class EquipRefusal(StrEnum):
    NOT_A_PC = "not_a_pc"
    NOT_CARRIED = "not_carried"
    NOT_EQUIPMENT = "not_equipment"
    ALREADY_EQUIPPED = "already_equipped"
    NOT_EQUIPPED = "not_equipped"
    NOT_HERE = "not_here"


class EquipRefused(ValueError):
    def __init__(self, reason: EquipRefusal, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


def _has(item: SrdEquipment | None, prop: str) -> bool:
    return item is not None and any(p.index == prop for p in item.properties)


def _two_handed(item: SrdEquipment | None) -> bool:
    return _has(item, "two-handed")


def _gear_ac(creature: Creature, gear: Equipped, regs: CharacterRegistries) -> int:
    armor = regs.equipment.find(gear.armor) if gear.armor else None
    shield = regs.equipment.find(gear.shield) if gear.shield else None
    base = armor_class(creature.abilities, armor=armor, shield=shield)
    return base + feature_ac_bonus(creature, regs.features, armored=armor is not None)


def _changed(creature: Creature, gear: Equipped, regs: CharacterRegistries) -> EquipmentChanged:
    old = creature.pc.equipped if creature.pc is not None else Equipped()
    ac = creature.ac + _gear_ac(creature, gear, regs) - _gear_ac(creature, old, regs)
    return EquipmentChanged(creature_id=creature.id, equipped=gear, ac=max(0, ac))


def _wear(gear: Equipped, item: SrdEquipment, regs: CharacterRegistries) -> Equipped:
    held = gear.model_copy()
    if item.armor_category == SHIELD:
        held.shield, held.off_hand = item.index, None
        if _two_handed(regs.equipment.find(held.main_hand or "")):
            held.main_hand = None
    elif item.armor_category is not None and item.armor_class is not None:
        held.armor = item.index
    elif item.damage is not None and item.weapon_range == "Ranged":
        held.ranged = item.index
    elif item.damage is not None:
        held.main_hand = item.index
        if _two_handed(item):
            held.off_hand, held.shield = None, None
        elif not _has(item, "light"):
            held.off_hand = None
    else:
        raise EquipRefused(EquipRefusal.NOT_EQUIPMENT, f"{item.name} cannot be worn or wielded")
    return held


def _hero(creature: Creature) -> Equipped:
    if creature.pc is None:
        raise EquipRefused(EquipRefusal.NOT_A_PC, f"{creature.name} has no gear slots")
    return creature.pc.equipped


def equip_events(creature: Creature, item: str, regs: CharacterRegistries) -> list[AnyEvent]:
    gear = _hero(creature)
    if carried_qty(creature, item) < 1:
        raise EquipRefused(EquipRefusal.NOT_CARRIED, f"{creature.name} does not carry {item}")
    entry = regs.equipment.find(item)
    if entry is None:
        raise EquipRefused(EquipRefusal.NOT_EQUIPMENT, f"{item} cannot be worn or wielded")
    new = _wear(gear, entry, regs)
    if new.main_hand == new.off_hand == item and carried_qty(creature, item) < 2:
        new.off_hand = None
    if new == gear:
        raise EquipRefused(EquipRefusal.ALREADY_EQUIPPED, f"{entry.name} is already in hand")
    return [_changed(creature, new, regs)]


def draw_events(creature: Creature, item: str, regs: CharacterRegistries) -> list[AnyEvent]:
    entry = regs.equipment.find(item)
    if entry is None or entry.weapon_category is None:
        raise EquipRefused(EquipRefusal.NOT_EQUIPMENT, f"{item} is not a weapon")
    try:
        return equip_events(creature, item, regs)
    except EquipRefused as refused:
        if refused.reason is EquipRefusal.ALREADY_EQUIPPED:
            return []
        raise


def unequip_events(creature: Creature, item: str, regs: CharacterRegistries) -> list[AnyEvent]:
    gear = _hero(creature)
    held = gear.model_copy()
    for slot in _SLOTS:
        if getattr(held, slot) == item:
            setattr(held, slot, None)
    if held == gear:
        raise EquipRefused(EquipRefusal.NOT_EQUIPPED, f"{item} is not equipped")
    return [_changed(creature, held, regs)]


def release_events(
    creature: Creature, item: str, regs: CharacterRegistries, qty: int = 1
) -> list[AnyEvent]:
    """Free the slots holding `item` (the off hand first) that `qty` fewer copies cannot fill
    (M29.7a: handing several away; one copy for a drop or a throw)."""
    gear = _hero(creature)
    worn = [slot for slot in _SLOTS if getattr(gear, slot) == item]
    extra = len(worn) - max(0, carried_qty(creature, item) - qty)
    if not worn or extra <= 0:
        return []
    held = gear.model_copy()
    for slot in sorted(worn, key=lambda s: s != "off_hand")[:extra]:
        setattr(held, slot, None)
    return [_changed(creature, held, regs)]


def drop_events(
    state: GameState, creature: Creature, item: str, regs: CharacterRegistries
) -> list[AnyEvent]:
    carried = carried_qty(creature, item)
    if carried < 1:
        raise EquipRefused(EquipRefusal.NOT_CARRIED, f"{creature.name} does not carry {item}")
    events = release_events(creature, item, regs)
    entry = regs.equipment.find(item)
    name = entry.name if entry is not None else item.replace("-", " ")
    placed = WorldItem(
        id=f"dropped-{item}-{state.event_count}",
        name=name,
        catalog_id=item,
        node_id=state.world.current_node,
    )
    events.append(InventoryChanged(creature_id=creature.id, item=item, delta=-1, qty=carried - 1))
    events.append(ItemPlaced(item=placed))
    return events


def take_events(
    state: GameState, creature: Creature, item_id: str, qty: int | None = None
) -> list[AnyEvent]:
    """`creature` picks up the visible world item `item_id` lying at the current place (`qty`
    units of its stack; None or the whole count takes it all)."""
    _hero(creature)
    item = state.world.items.get(item_id)
    here = state.world.current_node
    if item is None or item.hidden or item.node_id != here:
        raise EquipRefused(EquipRefusal.NOT_HERE, "that is not lying here")
    if qty is not None and 0 < qty < item.qty and item.catalog_id is not None:
        have = carried_qty(creature, item.catalog_id) + qty
        return [
            ItemRemoved(item_id=item.id, qty=qty),
            InventoryChanged(creature_id=creature.id, item=item.catalog_id, delta=qty, qty=have),
        ]
    gone = ItemRemoved(item_id=item.id)
    if item.catalog_id is None:
        keepsake = Keepsake(
            id=item.id, name=item.name[:40], quest_id=item.quest_id, teaches=item.teaches
        )
        gained = KeepsakeGained(creature_id=creature.id, keepsake=keepsake)
        return [gone, gained, *lore_events(creature.id, keepsake)]  # M29.9b T13: a clue
    qty = carried_qty(creature, item.catalog_id) + item.qty
    stack = InventoryChanged(creature_id=creature.id, item=item.catalog_id, delta=item.qty, qty=qty)
    return [gone, stack]
