"""Fight menu entries for items (M36.2, SPEC 6.2). Pure.

- `item:<item>`: a consumable the hero carries (data/bg3/consumables.json: healing potions,
  poultices), drunk or given as a bonus action: the hero, or an ally in reach (an ally further
  away is an approach target, `menu_probe`).
- `use:<use_id>`: each fight use of the hero's gear the sheet lists (`rules.gear_menu`: thrown
  flasks, oil, ball bearings, lighting a torch, the healer's kit), aimed by its own target kind
  (none, a creature, an ally, a zone) and accepted by the real `use_item` command.
- `throw:<item>` (M36.10b): any other carried item thrown at a foe as an improvised weapon
  (data/bg3/item_uses.json `improvised`, SRD 5.1 "Improvised Weapons": 1d4 + STR, the item is
  spent). Weapons and armour are thrown from the attack entries, a consumable is drunk
  (`item:`), and an item with its own creature-aimed fight use has that `use:` entry; the real
  `use_item` command says which foes it accepts (a keepsake it refuses is not listed).

Public API: `item_entries(view) -> list[MenuEntry]`.
"""

from aidm.data.item_uses import improvised_use
from aidm.models.action_menu import ActionKind, EntryCost, MenuEntry
from aidm.models.commands import AnyCommand, UseItemCommand
from aidm.models.sheet import GearUseLine
from aidm.rules.item_effects import gear_name
from aidm.rules.menu_labels import item_label
from aidm.rules.menu_probe import Reach, probe_targets
from aidm.rules.menu_view import FightView, aim_of, is_spent
from aidm.rules.zones import MELEE_BAND


def _consumable_entries(view: FightView) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    party = (view.actor_id, *view.allies)
    for row in view.sheet.inventory:
        found = view.regs.consumables.find(row.item)
        if found is None or row.qty < 1 or any(e.item == row.item for e in out):
            continue
        item = row.item

        def command(cid: str, item: str = item) -> AnyCommand:
            return UseItemCommand(actor_id=view.actor_id, item=item, target_id=cid)

        reach = probe_targets(view.ready, view.actor_id, party, command, view.regs, MELEE_BAND)
        if not reach.listed:
            continue
        aim = aim_of(reach)
        out.append(
            MenuEntry(
                id=f"item:{item}",
                kind=ActionKind.ITEM,
                label=item_label(found.name, found.heal, row.qty),
                target_ids=aim.target_ids,
                max_targets=1,
                cost="bonus",
                spent=is_spent(view, "bonus"),
                target_notes=aim.notes,
                approach=aim.approach,
                item=item,
            )
        )
    return out


def _gear_reach(view: FightView, use: GearUseLine) -> Reach:
    def command(target: str) -> AnyCommand:
        zone = target if use.target == "zone" else None
        creature = target if use.target in ("creature", "ally") else None
        return UseItemCommand(
            actor_id=view.actor_id,
            item=use.item,
            use_id=use.use_id,
            target_id=creature,
            target_zone=zone,
        )

    if use.target == "zone":
        candidates: tuple[str, ...] = tuple(z.id for z in view.encounter.zone_map.zones)
    elif use.target == "ally":
        candidates = (view.actor_id, *view.allies)
    else:
        candidates = (*view.foes, *view.allies, view.actor_id)
    return probe_targets(view.ready, view.actor_id, candidates, command, view.regs)


def _gear_entry(view: FightView, use: GearUseLine) -> MenuEntry | None:
    cost: EntryCost = "bonus" if use.cost == "bonus" else "action"
    reach = Reach() if use.target == "none" else _gear_reach(view, use)
    if use.target != "none" and not reach.listed:
        return None
    word = "bonus action" if cost == "bonus" else "action"
    return MenuEntry(
        id=f"use:{use.use_id}",
        kind=ActionKind.GEAR,
        label=f"{use.label} ({word}, {use.qty} left)",
        target_ids=reach.listed,
        max_targets=0 if use.target == "none" else 1,
        cost=cost,
        spent=is_spent(view, cost),
        item=use.item,
        use_id=use.use_id,
    )


def _improvised_entry(view: FightView, item: str, qty: int) -> MenuEntry | None:
    use = improvised_use(item)

    def command(target: str) -> AnyCommand:
        return UseItemCommand(actor_id=view.actor_id, item=item, use_id=use.id, target_id=target)

    reach = probe_targets(view.ready, view.actor_id, view.foes, command, view.regs)
    if not reach.listed:
        return None
    aim = aim_of(reach)
    return MenuEntry(
        id=f"throw:{item}",
        kind=ActionKind.GEAR,
        label=f"Throw the {gear_name(item).lower()} (improvised weapon, action, {qty} carried)",
        target_ids=aim.target_ids,
        max_targets=1,
        spent=is_spent(view, "action"),
        target_notes=aim.notes,
        item=item,
        use_id=use.id,
    )


def _improvised_entries(view: FightView) -> list[MenuEntry]:
    aimed = {u.item for u in view.sheet.gear_uses if u.target == "creature"}
    out: list[MenuEntry] = []
    for row in view.sheet.inventory:
        item = row.item
        if row.qty < 1 or item in aimed or view.regs.consumables.find(item) is not None:
            continue
        if any(e.item == item for e in out):
            continue
        made = _improvised_entry(view, item, row.qty)
        if made is not None:
            out.append(made)
    return out


def item_entries(view: FightView) -> list[MenuEntry]:
    gear = [e for e in (_gear_entry(view, u) for u in view.sheet.gear_uses) if e is not None]
    return [*_consumable_entries(view), *gear, *_improvised_entries(view)]
