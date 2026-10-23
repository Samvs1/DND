"""Generated player-manual table of gear uses from data/bg3/item_uses.json (M27.8)."""

from aidm.data.item_catalogue import item_catalogue
from aidm.data.item_uses import (
    SCROLL_FAMILY,
    Boon,
    CastSpell,
    Craft,
    DamageUse,
    ItemUse,
    LightPlace,
    SurfaceUse,
    Unlock,
    item_use_data,
)
from aidm.data.manual_md import table, words

_WHEN = {
    "dark_place": "in a dark place",
    "locked": "at a locked thing",
    "place": "anywhere",
    "fight": "in a fight",
    "ally_down": "on a fallen ally",
    "long_rest": "at a long rest",
    "tagged_place": "at a fitting place",
}
_PLAIN = {
    "reveal_map": "charts the way ahead",
    "stabilize": "stabilizes a dying ally",
    "supplies": "adds camp supplies",
    "condition": "puts a condition on the target",
    "ignite": "fire into a zone (sets oil alight)",
    "unpack": "opens the pack into its contents",
}


def item_name(item: str) -> str:
    if item == SCROLL_FAMILY:
        return "Spell scroll (any)"
    found = item_catalogue().find(item)
    return found.name if found is not None else words(item)


def when_text(use: ItemUse) -> str:
    return _WHEN.get(use.when, use.when)


def effect_text(use: ItemUse) -> str:
    e = use.effect
    if isinstance(e, LightPlace):
        return "lights the place; shows you to anything waiting"
    if isinstance(e, Boon):
        goal = e.skills or e.saves_against
        return f"advantage on {', '.join(words(s) for s in goal)}"
    if isinstance(e, SurfaceUse):
        return f"leaves {words(e.surface)} in a zone"
    if isinstance(e, DamageUse):
        return f"{e.dice} {e.damage_type} damage"
    if isinstance(e, Unlock):
        return f"{e.method}s the lock" if e.method != "key" else "opens with a key"
    if isinstance(e, Craft):
        return f"makes {words(e.output)} from {e.supplies} camp supplies"
    if isinstance(e, CastSpell):
        return "casts the scroll's spell"
    return _PLAIN.get(e.kind, e.kind)


def item_uses_table() -> str:
    rows = [
        [
            item_name(u.item),
            u.label,
            when_text(u),
            {"action": "Action", "bonus": "Bonus action"}.get(u.cost or "", "-"),
            effect_text(u),
        ]
        for u in item_use_data().uses
    ]
    return table(["Item", "Use", "Where", "Cost in a fight", "What it does"], rows)
