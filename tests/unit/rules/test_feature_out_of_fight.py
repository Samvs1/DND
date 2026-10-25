"""Class features out of a fight (M36.4): Second Wind heals the same way as in a fight (the same
hook, resource and dice, no turn economy); a feature that needs a fight is refused plainly and
left off the explore menu. Lay on Hands has no class in this game (no paladin), so the healing
feature at hand is Second Wind.
"""

import random

import pytest

from aidm.data.combat_data import combat_registries
from aidm.models.action_menu import MenuChoice, MenuStep
from aidm.models.combat_events import FeatureUsed
from aidm.models.commands import RefusalCode
from aidm.models.dice import RollKind
from aidm.models.events import DiceRolled, EconomyChanged
from aidm.models.state import GameState
from aidm.rules.action_menu import build_menu
from aidm.rules.acts import FeatureUseIntent
from aidm.rules.command_checks import CommandRefused
from aidm.rules.feature_commands import explore_feature_events
from aidm.rules.menu_steps import to_acts
from aidm.session.reducer import apply
from tests.session.playtest_saves import replay_until

REGS = combat_registries()


def _hurt_brienne(hp: int = 9) -> GameState:
    """full 469: out of a fight; Brienne (fighter, Second Wind 1/1) hurt to `hp`."""
    state = replay_until("m35-r6-full", 469)
    brienne = state.creatures["pc-p2"].model_copy(update={"hp": hp})
    return state.model_copy(update={"creatures": {**state.creatures, "pc-p2": brienne}})


def test_second_wind_heals_out_of_a_fight() -> None:
    state = _hurt_brienne()
    events = explore_feature_events(state, "pc-p2", "second-wind", REGS, random.Random(4))
    assert not any(isinstance(e, EconomyChanged) for e in events)
    used = next(e for e in events if isinstance(e, FeatureUsed))
    assert used.feature == "second-wind" and used.target_ids == ("pc-p2",)
    heal = next(e for e in events if isinstance(e, DiceRolled))
    assert heal.kind is RollKind.HEAL
    live = state.model_copy(deep=True)
    for event in events:
        apply(live, event)
    brienne = live.creatures["pc-p2"]
    assert brienne.resources["second-wind"].current == 0
    assert brienne.hp == min(brienne.max_hp, 9 + heal.roll.total)


def test_second_wind_out_of_a_fight_refusals() -> None:
    full = replay_until("m35-r6-full", 469)
    with pytest.raises(CommandRefused) as at_full:
        explore_feature_events(full, "pc-p2", "second-wind", REGS, random.Random(1))
    assert at_full.value.code is RefusalCode.FULL_HP
    with pytest.raises(CommandRefused) as surge:
        explore_feature_events(_hurt_brienne(), "pc-p2", "action-surge", REGS, random.Random(1))
    assert surge.value.code is RefusalCode.NOT_IN_COMBAT
    assert surge.value.reason == "Action Surge is only of use in a fight."
    state = _hurt_brienne()
    spent = explore_feature_events(state, "pc-p2", "second-wind", REGS, random.Random(2))
    for event in spent:
        state = apply(state.model_copy(deep=True), event)
    state = state.model_copy(
        update={
            "creatures": {
                **state.creatures,
                "pc-p2": state.creatures["pc-p2"].model_copy(update={"hp": 3}),
            }
        }
    )
    with pytest.raises(CommandRefused) as rest:
        explore_feature_events(state, "pc-p2", "second-wind", REGS, random.Random(1))
    assert rest.value.code is RefusalCode.ABILITY_SPENT
    fight = replay_until("m35-r6-typed", 435)
    with pytest.raises(CommandRefused, match="on your turn"):
        explore_feature_events(fight, "pc-p2", "second-wind", REGS, random.Random(1))


def test_menu_lists_second_wind_out_of_a_fight_and_steps_use_it() -> None:
    state = _hurt_brienne()
    menu = build_menu(state, "pc-p2", REGS)
    wind = next(e for e in menu.entries if e.id == "feature:second-wind")
    assert wind.feature_id == "second-wind" and wind.label.startswith("Second Wind (heals 1d10")
    assert not any(e.id == "feature:action-surge" for e in menu.entries)
    acts = to_acts(state, menu, MenuChoice(steps=(MenuStep(entry=wind.id),)), REGS)
    assert acts == [FeatureUseIntent("pc-p2", "second-wind")]


def test_menu_leaves_fight_only_features_off_the_explore_menu() -> None:
    """typed 1100 (out of a fight): the cleric's Turn Undead aims at the fight's zones."""
    menu = build_menu(replay_until("m35-r6-typed", 1100), "pc-p8", REGS)
    assert not any(e.id.startswith("feature:") for e in menu.entries)
