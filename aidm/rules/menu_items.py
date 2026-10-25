"""Item entries of the out-of-fight menu: give, hand, pay, take, lift, gear, potions (M36.3, SPEC
6.2). Pure. Built from the hero's sheet (the item cards' own source) and the place.

- `give:<item>`: every carried inventory item (`qty_max` the count carried, round 6 Y13: "a block
  of incense" out of five) and every keepsake (grouped by name, `item` the first one's id) to a
  person standing here (`rules.handing.give_events`);
- `hand:<item>`, `hand:gold`: the same to another hero (`rules.hero_handing.hand_events`);
- `pay`: gold to a person here (`qty_max` the gold carried, `rules.paying.pay_events`);
- `take:<name>`: each visible item lying here, items of one name and kind grouped (M36.4, round 6
  Y12: three lumps of resin are one entry, `qty_max` 3; `item` the first one's id,
  `same_lying` finds the rest), `qty_max` the count (`rules.equipment.take_events`, counted);
- `loot:<item>` (M36.4, round 6 Y14): each thing in a downed or dead hero's pack (keepsakes
  grouped by name, `loot:gold` the coins), aimed at that hero (`rules.hero_handing.loot_events`);
- `lift:<keepsake>`: a keepsake a person here holds, taken back (`rules.lifting.lift_events`);
- `equip:<item>` (a weapon, armour or shield not in hand), `unequip:<item>`, `drop:<item>`
  (`qty_max` the count carried; one unit per drop, `rules.equipment`);
- `item:<consumable>`: a potion or poultice on the hero or another hero (`rules.items`);
- `use:<use_id>`: each use of carried gear made out of a fight, in the place (the item card's Use
  button, `rules.gear_menu.item_use_hints`); a use on a lock aims at a locked thing here;
- `put_out`: putting out the hero's carried light (free, on any turn);
- `copy:<scroll>`: a wizard copying a carried scroll into the spellbook (`rules.scrolls`).
Labels say what the cards say: names, counts, gold, healing dice.

Public API: `carried_entries(view) -> list[MenuEntry]`, `put_out_entries(state, actor_id)`,
`same_keepsakes(keepsakes, first_id)`, `same_lying(state, first_id)` (the group of an entry).
"""

from collections.abc import Sequence

from aidm.models.action_menu import ActionKind, MenuEntry
from aidm.models.character import Keepsake
from aidm.models.sheet import InventoryLine
from aidm.models.state import Creature, GameState
from aidm.models.world import WorldItem
from aidm.rules.item_effects import gear_name
from aidm.rules.light import hero_light
from aidm.rules.menu_scene_view import SceneMenuView, fallen_heroes
from aidm.rules.menu_view import slug
from aidm.rules.scene import current_scene


def _keepsake_key(keepsake: Keepsake) -> str:
    return slug(keepsake.name) or slug(keepsake.id)


def same_keepsakes(keepsakes: Sequence[Keepsake], first_id: str) -> list[str]:
    """The ids of the keepsakes grouped with `first_id` (same name), `first_id` first."""
    first = next((k for k in keepsakes if k.id == first_id), None)
    if first is None:
        return []
    key = _keepsake_key(first)
    return [first_id, *(k.id for k in keepsakes if k.id != first_id and _keepsake_key(k) == key)]


def _lying_key(item: WorldItem) -> tuple[str, str | None]:
    return slug(item.name) or slug(item.id), item.catalog_id


def same_lying(state: GameState, first_id: str) -> list[WorldItem]:
    """The visible items lying here grouped with `first_id` (same name and kind), it first."""
    world = state.world
    here = [world.items[i] for i in current_scene(state).item_ids]
    first = next((i for i in here if i.id == first_id), None)
    if first is None:
        return []
    key = _lying_key(first)
    return [first, *(i for i in here if i.id != first_id and _lying_key(i) == key)]


def _with_keepsakes(
    out: list[tuple[str, str, int]], keepsakes: Sequence[Keepsake]
) -> list[tuple[str, str, int]]:
    groups: dict[str, list[str]] = {}
    for keepsake in keepsakes:
        groups.setdefault(_keepsake_key(keepsake), []).append(keepsake.id)
    taken = {key for key, _, _ in out}
    for key, ids in groups.items():
        out.append((key if key not in taken else f"{key}-keepsake", ids[0], len(ids)))
    return out


def _pack(hero: Creature) -> list[tuple[str, str, int]]:
    """(entry key, item or keepsake id, count) for every thing in a hero's pack."""
    pc = hero.pc
    if pc is None:
        return []
    rows = [(row.item, row.item, row.qty) for row in pc.inventory if row.qty > 0]
    return _with_keepsakes(rows, pc.keepsakes)


def _carried(view: SceneMenuView) -> list[tuple[str, str, int]]:
    """(entry key, item or keepsake id, count) for every thing the hero can hand over."""
    rows = [(row.item, row.item, row.qty) for row in view.sheet.inventory if row.qty > 0]
    pc = view.state.creatures[view.actor_id].pc
    return _with_keepsakes(rows, pc.keepsakes if pc is not None else [])


def _name(view: SceneMenuView, thing: str) -> str:
    row = next((r for r in view.sheet.inventory if r.item == thing), None)
    if row is not None:
        return row.name
    keepsake = next((k for k in view.sheet.keepsakes if k.id == thing), None)
    return keepsake.name if keepsake is not None else thing.replace("-", " ")


def _handing(view: SceneMenuView) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    for key, thing, count in _carried(view):
        name = _name(view, thing)
        carry = f"(you carry {count})"
        if view.people:
            out.append(
                MenuEntry(
                    id=f"give:{key}",
                    kind=ActionKind.GIVE,
                    label=f"Give {name} {carry}",
                    target_ids=view.people,
                    max_targets=1,
                    qty_max=count,
                    item=thing,
                )
            )
        if view.heroes:
            out.append(
                MenuEntry(
                    id=f"hand:{key}",
                    kind=ActionKind.HAND,
                    label=f"Hand {name} to another hero {carry}",
                    target_ids=view.heroes,
                    max_targets=1,
                    qty_max=count,
                    item=thing,
                )
            )
    return out


def _gold(view: SceneMenuView) -> list[MenuEntry]:
    gold = view.gold
    if gold < 1:
        return []
    out: list[MenuEntry] = []
    if view.heroes:
        label = f"Hand gold to another hero (you have {gold} gp)"
        out.append(
            MenuEntry(
                id="hand:gold",
                kind=ActionKind.HAND,
                label=label,
                target_ids=view.heroes,
                max_targets=1,
                qty_max=gold,
            )
        )
    if view.people:
        label = f"Pay gold to someone here (you have {gold} gp)"
        out.append(
            MenuEntry(
                id="pay",
                kind=ActionKind.PAY,
                label=label,
                target_ids=view.people,
                max_targets=1,
                qty_max=gold,
            )
        )
    return out


def _lying(view: SceneMenuView) -> list[MenuEntry]:
    world = view.state.world
    out: list[MenuEntry] = []
    seen: set[str] = set()
    for item_id in current_scene(view.state).item_ids:
        if item_id in seen:
            continue
        group = same_lying(view.state, item_id)
        seen.update(i.id for i in group)
        item, count = group[0], sum(i.qty for i in group)
        out.append(
            MenuEntry(
                id=f"take:{_lying_key(item)[0]}",
                kind=ActionKind.TAKE,
                label=f"Pick up {item.name} ({count} here)",
                qty_max=count,
                item=item.id,
            )
        )
    for npc_id in view.people:
        for keepsake in world.npcs[npc_id].keepsakes:
            out.append(
                MenuEntry(
                    id=f"lift:{slug(keepsake.id)}",
                    kind=ActionKind.LIFT,
                    label=f"Take back {keepsake.name} from {world.npcs[npc_id].name}",
                    target_ids=(npc_id,),
                    max_targets=1,
                    item=keepsake.id,
                )
            )
    return out


def _gear_changes(view: SceneMenuView, row: InventoryLine) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    entry = view.regs.chars.equipment.find(row.item)
    wearable = entry is not None and (entry.damage is not None or entry.armor_category is not None)
    if row.equipped_slot is not None:
        label = f"Stow {row.name} (in use: {row.equipped_slot.replace('_', ' ')})"
        out.append(
            MenuEntry(id=f"unequip:{row.item}", kind=ActionKind.UNEQUIP, label=label, item=row.item)
        )
    elif wearable:
        label = f"Equip {row.name}"
        out.append(
            MenuEntry(id=f"equip:{row.item}", kind=ActionKind.EQUIP, label=label, item=row.item)
        )
    out.append(
        MenuEntry(
            id=f"drop:{row.item}",
            kind=ActionKind.DROP,
            label=f"Drop {row.name} (you carry {row.qty})",
            qty_max=max(1, row.qty),
            item=row.item,
        )
    )
    return out


def _potion(view: SceneMenuView, row: InventoryLine) -> MenuEntry | None:
    found = view.regs.consumables.find(row.item)
    if found is None or row.qty < 1:
        return None
    heal = f"heals {found.heal}, " if found.heal else ""
    return MenuEntry(
        id=f"item:{row.item}",
        kind=ActionKind.ITEM,
        label=f"{found.name} ({heal}{row.qty} left)",
        target_ids=(view.actor_id, *view.heroes),
        max_targets=1,
        item=row.item,
    )


def _uses(view: SceneMenuView, row: InventoryLine) -> list[MenuEntry]:
    locks = tuple(
        f
        for f in current_scene(view.state).feature_ids
        if view.state.world.features[f].lock is not None
    )
    out: list[MenuEntry] = []
    for hint in row.uses:
        aimed = locks if hint.when == "locked" else ()
        out.append(
            MenuEntry(
                id=f"use:{hint.use_id}",
                kind=ActionKind.GEAR,
                label=f"{hint.label} ({gear_name(row.item)}, {row.qty} carried)",
                target_ids=aimed,
                max_targets=1 if aimed else 0,
                item=row.item,
                use_id=hint.use_id,
            )
        )
    return out


def _copies(view: SceneMenuView) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    for line in view.sheet.scroll_copies:
        label = f"Copy {line.name} into your spellbook (level {line.level}, {line.cost} gp)"
        out.append(
            MenuEntry(
                id=f"copy:{line.item}",
                kind=ActionKind.COPY_SCROLL,
                label=label,
                note="" if line.affordable else "not enough gold",
                item=line.item,
                spell_id=line.spell,
            )
        )
    return out


def put_out_entries(state: GameState, actor_id: str) -> list[MenuEntry]:
    light = hero_light(state, actor_id)
    if light is None:
        return []
    name = gear_name(light.item)
    return [
        MenuEntry(
            id="put_out",
            kind=ActionKind.PUT_OUT,
            label=f"Put out your light ({name}, free)",
            cost="free",
            item=light.item,
        )
    ]


def _loot(view: SceneMenuView) -> list[MenuEntry]:
    """M36.4 Y14: what lies in a downed or dead hero's pack, out of a fight."""
    out: list[MenuEntry] = []
    for hero_id in fallen_heroes(view):
        hero = view.state.creatures[hero_id]
        keep = {k.id: k.name for k in hero.pc.keepsakes} if hero.pc is not None else {}
        for key, thing, count in _pack(hero):
            name = keep.get(thing) or gear_name(thing)
            out.append(
                MenuEntry(
                    id=f"loot:{key}",
                    kind=ActionKind.TAKE,
                    label=f"Take {name} from {hero.name}'s pack ({hero.name} carries {count})",
                    target_ids=(hero_id,),
                    max_targets=1,
                    qty_max=count,
                    item=thing,
                )
            )
        gold = hero.pc.gold if hero.pc is not None else 0
        if gold > 0:
            label = f"Take gold from {hero.name}'s pack ({hero.name} has {gold} gp)"
            out.append(
                MenuEntry(
                    id="loot:gold",
                    kind=ActionKind.TAKE,
                    label=label,
                    target_ids=(hero_id,),
                    max_targets=1,
                    qty_max=gold,
                )
            )
    return out


def carried_entries(view: SceneMenuView) -> list[MenuEntry]:
    out = [*_handing(view), *_gold(view), *_lying(view), *_loot(view)]
    for row in view.sheet.inventory:
        out += _gear_changes(view, row)
        potion = _potion(view, row)
        out += [potion] if potion is not None else []
        out += _uses(view, row)
    out += put_out_entries(view.state, view.actor_id)
    out += _copies(view)
    return out
