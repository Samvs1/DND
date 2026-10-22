"""The hero's gear uses in a fight, for the hotbar Items section (M27.6, GOAL_ITEMS "What players
see": "the hotbar Items section lists combat uses with their cost").

`fight_gear_lines(creature, light_item)` lists, per carried catalogue item, each use of
data/bg3/item_uses.json that has a fight cost (action / bonus), is wired and is not a long-rest
use, with what it is aimed at (`target_kind`, read from the effect kind, never per item). A
`from_light` use (throw the lit torch) is listed only while the hero's carried light is that
item (`light_item`), and lighting uses are hidden while the hero already carries a light (one
light per hero). Whether a use fits right now is the interpreter's call when it is sent
(`rules.item_use.use_item`); a refusal is shown then.

M27.7: a spell scroll (`cast_spell`) is aimed as its spell is: an area or point spell cast at a
range takes a zone, a creature spell takes a creature (a foe or a friend), a self spell nothing.

Public API: `target_kind(use, item=None) -> GearTarget`, `fight_gear_lines(creature,
light_item=None)`.
"""

from aidm.data.item_uses import (
    CastSpell,
    ConditionUse,
    DamageUse,
    Ignite,
    ItemUse,
    LightPlace,
    Stabilize,
    SurfaceUse,
    uses_for_item,
)
from aidm.data.spell_defs import spell_defs
from aidm.models.sheet import GearTarget, GearUseLine, ItemUseHint
from aidm.models.state import Creature
from aidm.rules.item_effects import gear_name
from aidm.rules.scrolls import scroll_spell_index


def _spell_target(spell_id: str | None) -> GearTarget:
    spell = spell_defs().find(spell_id) if spell_id else None
    if spell is None or spell.targeting.kind == "self":
        return "none"
    if spell.targeting.kind in ("area", "point"):
        return "none" if spell.range.kind == "self" else "zone"
    return "creature"


def target_kind(use: ItemUse, item: str | None = None) -> GearTarget:
    match use.effect:
        case CastSpell(spell=spell):
            return _spell_target(spell or scroll_spell_index(item or ""))
        case DamageUse() | ConditionUse():
            return "creature"
        case Stabilize():
            return "ally"
        case SurfaceUse() | Ignite():
            return "zone"
        case _:
            return "none"


def _listed(use: ItemUse, in_pack: bool, light_item: str | None) -> bool:
    if use.cost is None or use.when == "long_rest":
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
                    target=target_kind(use, item),
                    qty=1 if use.from_light else held.get(item, 0),
                    effect=use.effect.kind,
                )
            )
    return lines


HERE_WHEN = frozenset({"dark_place", "place", "locked", "tagged_place"})


def item_use_hints(item: str) -> list[ItemUseHint]:
    """The uses the item card offers (M27.8): the ones made out of a fight, in the place."""
    return [
        ItemUseHint(use_id=u.id, label=u.label, when=u.when, verb=u.verbs[0] if u.verbs else "use")
        for u in uses_for_item(item)
        if u.when in HERE_WHEN
    ]
