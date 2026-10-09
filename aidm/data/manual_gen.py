"""Splice generated tables into docs/PLAYER_MANUAL.md between marker comments (M14.1).

A generated block starts with `<!-- generated:<name> -->` and ends with `<!-- end generated:<name> -->`.
The text outside the markers is hand-written and never touched.

Public API: `SECTIONS`, `MANUAL_PATH`, `render`, `splice`, `stale_sections`.
"""

import re
from collections.abc import Callable
from pathlib import Path

from aidm.data import manual_ref, manual_rules

MANUAL_PATH = Path(__file__).resolve().parents[2] / "docs" / "PLAYER_MANUAL.md"

SECTIONS: dict[str, Callable[[], str]] = {
    "classes": manual_ref.classes_table,
    "class_features": manual_ref.class_features_table,
    "spell_slots": manual_ref.spell_slots_table,
    "races": manual_ref.races_table,
    "backgrounds": manual_ref.backgrounds_table,
    "conditions": manual_rules.conditions_table,
    "surfaces": manual_rules.surfaces_table,
    "surface_mixes": manual_rules.surface_mixes_list,
    "spells": manual_rules.spells_table,
    "consumables": manual_rules.consumables_table,
    "shop_rules": manual_rules.shop_rules,
    "scribe_prices": manual_rules.scribe_prices,
}


def _pattern(name: str) -> re.Pattern[str]:
    start, end = f"<!-- generated:{name} -->", f"<!-- end generated:{name} -->"
    return re.compile(re.escape(start) + r"\n(?:.*?\n)?" + re.escape(end), re.DOTALL)


def render(name: str) -> str:
    return f"<!-- generated:{name} -->\n{SECTIONS[name]()}\n<!-- end generated:{name} -->"


def splice(text: str, names: list[str] | None = None) -> str:
    """The text with every (or the named) generated block rewritten from the data."""
    for name in names if names is not None else list(SECTIONS):
        block = render(name)
        text = _pattern(name).sub(lambda _m, b=block: b, text)
    return text


def stale_sections(text: str) -> list[str]:
    """Names of blocks that are missing or differ from what the data produces."""
    stale: list[str] = []
    for name in SECTIONS:
        found = _pattern(name).search(text)
        if found is None or found.group(0) != render(name):
            stale.append(name)
    return stale
