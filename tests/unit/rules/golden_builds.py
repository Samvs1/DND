"""The six fixed golden builds (human, standard array) levelled 1 -> 5 with the scripted choices.

Shared by the per-class goldens (test_golden_classes) and the export/import round trip.
"""

from __future__ import annotations

import functools

from aidm.data.character_data import character_registries
from aidm.models.abilities import Ability
from aidm.models.events import CreatureAdded
from aidm.models.state import Creature, GameState
from aidm.rules.creation import build_character
from aidm.session.reducer import apply
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.leveling_fixtures import level_to

REGS = character_registries()
GOLDEN_CLASSES = ("fighter", "rogue", "wizard", "cleric", "ranger", "warlock")

# Standard array 15, 14, 13, 12, 10, 8 assigned by class priority (before the human +1 to all).
_ASSIGNMENT: dict[str, tuple[str, ...]] = {
    "fighter": ("str", "con", "dex", "wis", "cha", "int"),
    "rogue": ("dex", "con", "cha", "int", "wis", "str"),
    "wizard": ("int", "con", "dex", "wis", "cha", "str"),
    "cleric": ("wis", "con", "str", "cha", "dex", "int"),
    "ranger": ("dex", "wis", "con", "str", "int", "cha"),
    "warlock": ("cha", "con", "dex", "wis", "int", "str"),
}
_ARRAY = (15, 14, 13, 12, 10, 8)


@functools.cache
def golden_levels(class_index: str) -> dict[int, Creature]:
    """The golden PC of `class_index` as it stands at each level 1..5 (independent copies)."""
    scores = {Ability(a): v for a, v in zip(_ASSIGNMENT[class_index], _ARRAY, strict=True)}
    choices = default_choices(class_index, "human", None).model_copy(update={"base_scores": scores})
    pc = build_character(choices, REGS, "pc1")
    state = apply(GameState(campaign_id="golden", seed=1), CreatureAdded(creature=pc))
    levels = {1: state.creatures["pc1"].model_copy(deep=True)}
    for level in range(2, 6):
        level_to(state, "pc1", level, REGS, [])
        levels[level] = state.creatures["pc1"].model_copy(deep=True)
    return levels
