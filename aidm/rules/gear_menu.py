"""The hero's gear uses in a fight, for the hotbar Items section (M27.6, GOAL_ITEMS "What players
see": "the hotbar Items section lists combat uses with their cost").

`fight_gear_lines(creature, light_item)` lists, per carried catalogue item, each use of
data/bg3/item_uses.json that has a fight cost (action / bonus), is wired and is not a long-rest
use, with what it is aimed at (`target_kind`, read from the effect kind, never per item). A
`from_light` use (throw the lit torch) is listed only while the hero's carried light is that
item (`light_item`), and lighting uses are hidden while the hero already carries a light (one
light per hero). Whether a use fits right now is the interpreter's call when it is sent
(`rules.item_use.use_item`); a refusal is shown then.

Public API: `target_kind(use) -> GearTarget`, `fight_gear_lines(creature, light_item=None)`.
"""

from aidm.data.item_uses import (
    ConditionUse,
    DamageUse,
    Ignite,
    ItemUse,
    LightPlace,
    Stabilize,
    SurfaceUse,
    uses_for_item,
)
from aidm.models.sheet import GearTarget, GearUseLine
from aidm.models.state import Creature
from aidm.rules.item_effects import gear_name, not_wired


def target_kind(use: ItemUse) -> GearTarget:
    match use.effect:
        case DamageUse() | ConditionUse():
            return "creature"
        case Stabilize():
            return "ally"
        case SurfaceUse() | Ignite():
            return "zone"
        case _:
            return "none"


def _listed(use: ItemUse, in_pack: bool, light_item: str | None) -> bool:
    if use.cost is None or use.when == "long_rest" or not_wired(use) is not None:
        return False
    if use.from_light:
        return light_item == use.item
    if isinstance(use.effect, LightPlace) and light_item is not None:
        return False
    return in_pack


def fight_gear_lines(creature: Creature, light_item: str | None = None) -> list[GearUseLine]:
    pc = creature.pc
    if pc is None:
        return []
    held = {entry.item: entry.qty for entry in pc.inventory}
    items = [*held, *([light_item] if light_item is not None and light_item not in held else [])]
    lines: list[GearUseLine] = []
    for item in items:
        for use in uses_for_item(item):
            if use.cost is None or not _listed(use, item in held, light_item):
                continue
            lines.append(
                GearUseLine(
                    item=item,
                    use_id=use.id,
                    name=gear_name(item),
                    label=use.label,
                    cost=use.cost,
                    target=target_kind(use),
                    qty=1 if use.from_light else held.get(item, 0),
                )
            )
    return lines
