"""Plain-language tooltip text for items and the item uses of data/bg3/item_uses.json (M28.1).

The use text reuses the player manual's builders (`aidm.data.manual_uses`), so the manual table and
the tips say the same thing. Pure: no I/O.

Public API: `item_tip(item) -> Tip`, `use_tip(use) -> Tip`.
"""

from aidm.data.item_catalogue import CatalogueItem
from aidm.data.item_uses import ItemUse, LightPlace, item_substances, uses_for_item
from aidm.data.manual_uses import effect_text, item_name, when_text
from aidm.models.tips import Tip

_COST = {"action": "an action", "bonus": "a bonus action"}


def _sentence(text: str) -> str:
    return text[0].upper() + text[1:] + "."


def _lifecycle(use: ItemUse) -> str:
    if use.from_light:
        return f"Uses your lit {item_name(use.item).lower()}: the light goes out."
    parts: list[str] = []
    if isinstance(use.effect, LightPlace):
        parts.append("Stays lit and travels with you until a long rest")
    if use.consumes:
        parts.append(
            "used up when lit" if isinstance(use.effect, LightPlace) else "used up when used"
        )
    elif use.charges is not None:
        parts.append(f"{use.charges} charges")
    elif isinstance(use.effect, LightPlace):
        parts.append("can be lit again later")
    if use.noise and not isinstance(use.effect, LightPlace):
        parts.append("it makes noise")
    return _sentence("; ".join(parts)) if parts else "Does not use the item up."


def use_tip(use: ItemUse) -> Tip:
    where = "" if use.cost and use.when == "fight" else " in a fight"
    cost = f"costs {_COST[use.cost]}{where}" if use.cost else "not a fight action"
    lines = (
        _sentence(f"Used {when_text(use)}; {cost}"),
        _sentence(effect_text(use)),
        _lifecycle(use),
    )
    return Tip(title=use.label, lines=lines)


def _weight(w: float) -> str:
    return f", {w:g} lb" if w else ""


def item_tip(item: CatalogueItem) -> Tip:
    lines = [
        f"{item.category.value.capitalize()}{_weight(item.weight)}, worth {item.value_gp:g} gp."
    ]
    if item.heal:
        lines.append(f"Heals {item.heal}.")
    if item.supply:
        lines.append(
            f"Adds {item.supply} camp supply."
            if item.supply == 1
            else f"Adds {item.supply} camp supplies."
        )
    if item.opens:
        lines.append("Opens: " + ", ".join(o.replace("-", " ") for o in item.opens) + ".")
    uses = uses_for_item(item.id)
    if uses:
        lines.append("Uses: " + "; ".join(u.label.lower() for u in uses) + ".")
    subs = item_substances(item.id)
    if subs and len(lines) < 4:
        lines.append("Counts as: " + ", ".join(subs) + ".")
    return Tip(title=item.name, lines=tuple(lines[:4]))
