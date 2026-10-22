"""ONE pure builder of every tooltip text, keyed `<kind>:<id>` (M28.1, docs/next/GOAL_TOOLTIPS.md).

Kinds: `spell`, `item`, `use` (an item use), `condition`, `feature`, `surface`, `word`, `dc`,
`sheet`, `journal`. All text is built from the game data and the rules constants, never typed
twice: conditions and surfaces reuse the player manual's builders (`aidm.data.manual_rules`), item
uses reuse `aidm.data.manual_uses`, so the manual and the tips cannot drift. Pure: no I/O.

Public API: `build_tips() -> dict[str, Tip]` (fresh), `all_tips()` (cached), `tips_payload()`
(the JSON-able form served by `GET /api/tips`).
"""

import functools

from aidm.data.condition_defs import condition_defs
from aidm.data.feature_defs import feature_defs
from aidm.data.item_catalogue import item_catalogue
from aidm.data.item_uses import item_use_data
from aidm.data.manual_rules import condition_summary, surface_summary
from aidm.data.spell_defs import spell_defs
from aidm.data.surface_defs import surface_data
from aidm.models.tips import Tip
from aidm.rules.explain_items import item_tip, use_tip
from aidm.rules.explain_sheet import journal_tips, sheet_tips
from aidm.rules.explain_spells import spell_tip
from aidm.rules.explain_words import word_tips


def _conditions() -> dict[str, Tip]:
    return {
        f"condition:{c.index}": Tip(title=c.name, lines=(condition_summary(c),))
        for c in condition_defs().all()
    }


def _features() -> dict[str, Tip]:
    return {
        f"feature:{f.index}": Tip(title=f.name, lines=(f.summary,)) for f in feature_defs().all()
    }


def _surfaces() -> dict[str, Tip]:
    out: dict[str, Tip] = {}
    for s in surface_data().surfaces:
        text = surface_summary(s)
        out[f"surface:{s.index}"] = Tip(title=s.name, lines=(text[0].upper() + text[1:] + ".",))
    return out


def build_tips() -> dict[str, Tip]:
    tips: dict[str, Tip] = {}
    tips.update({f"spell:{s.index}": spell_tip(s) for s in spell_defs().all()})
    tips.update({f"item:{i.id}": item_tip(i) for i in item_catalogue().all()})
    tips.update({f"use:{u.id}": use_tip(u) for u in item_use_data().uses})
    tips.update(_conditions())
    tips.update(_features())
    tips.update(_surfaces())
    tips.update(word_tips())
    tips.update(sheet_tips())
    tips.update(journal_tips())
    return tips


@functools.cache
def all_tips() -> dict[str, Tip]:
    return build_tips()


def tips_payload() -> dict[str, dict[str, object]]:
    """`{key: {"title": ..., "lines": [...]}}`, the body of GET /api/tips."""
    return {k: {"title": t.title, "lines": list(t.lines)} for k, t in all_tips().items()}
