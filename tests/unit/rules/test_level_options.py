"""`level_up_options` offers exactly what `validate_level_up` accepts (M7.5 level-up dialog)."""

from __future__ import annotations

import pytest

from aidm.data.character_data import character_registries
from aidm.models.abilities import Ability
from aidm.models.events import CreatureAdded
from aidm.models.leveling import LevelUpChoices, LevelUpOptions, PickGroup
from aidm.models.state import Creature, GameState
from aidm.rules.creation import build_character
from aidm.rules.level_options import level_up_options
from aidm.rules.leveling import gain_xp, level_up, validate_level_up, xp_for_level
from aidm.session.reducer import apply
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.leveling_fixtures import level_to, run_events, script_choices

REGS = character_registries()
CLASSES = [c.index for c in REGS.classes.all()]


def _hero(cls: str) -> GameState:
    pc = build_character(default_choices(cls, "dwarf", "hill-dwarf"), REGS, "pc1")
    return apply(GameState(campaign_id="c", seed=1), CreatureAdded(creature=pc))


def _first(group: PickGroup | None) -> list[str]:
    return [o.id for o in group.options[: group.choose]] if group else []


def _choices_from(options: LevelUpOptions) -> LevelUpChoices:
    return LevelUpChoices(
        subclass=options.subclass.id if options.subclass else None,
        class_choices={g.id: _first(g) for g in options.class_choices},
        feature_choices={g.id: _first(g) for g in options.feature_choices},
        asi={Ability.STR: 2} if options.asi else {},
        cantrips=_first(options.cantrips),
        spells=_first(options.spells),
    )


def _ready(state: GameState, level: int) -> Creature:
    level_to(state, "pc1", level, REGS, [])
    creature = state.creatures["pc1"]
    run_events(
        state,
        gain_xp(creature, xp_for_level(level + 1) - (creature.pc.xp if creature.pc else 0)),
        [],
    )
    return state.creatures["pc1"]


def test_no_options_without_the_xp() -> None:
    creature = _hero("fighter").creatures["pc1"]
    assert level_up_options(creature, REGS) is None


@pytest.mark.parametrize("class_index", CLASSES)
def test_options_build_choices_the_server_accepts(class_index: str) -> None:
    state = _hero(class_index)
    for level in range(1, 5):
        creature = _ready(state, level)
        options = level_up_options(creature, REGS)
        assert options is not None and options.level == level + 1
        choices = _choices_from(options)
        # The ASI target is the test's own pick (STR +2), so only other fields must be clean.
        errors = validate_level_up(creature, choices, REGS)
        assert [e.field for e in errors if e.field != "asi"] == [], (class_index, level, errors)
        run_events(state, level_up(creature, script_choices(creature, REGS), REGS), [])


def test_subclass_and_asi_flags_follow_the_class_table() -> None:
    state = _hero("fighter")
    flags = []
    for level in range(1, 5):
        options = level_up_options(_ready(state, level), REGS)
        assert options is not None
        flags.append((options.level, options.subclass is not None, options.asi))
        creature = state.creatures["pc1"]
        run_events(state, level_up(creature, script_choices(creature, REGS), REGS), [])
    assert flags == [(2, False, False), (3, True, False), (4, False, True), (5, False, False)]


def test_wizard_options_list_spells_with_levels() -> None:
    state = _hero("wizard")
    options = level_up_options(_ready(state, 1), REGS)
    assert options is not None and options.spells is not None and options.prepared is not None
    assert options.spells.choose == 2 and options.spells.options
    assert all(o.level == 1 for o in options.spells.options)
    assert options.replace_from == []
