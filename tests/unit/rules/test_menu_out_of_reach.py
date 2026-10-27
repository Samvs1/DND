"""M40.2 round 7 Z2 (docs/playtests/M39_round7.md): a place the party has heard of that no open
road reaches is a not-offered target with the engine's reason, so a travel line naming it is
refused with that reason (M43.2 B2; the storyteller's before), never a stand-in place.
r7b-typed 649 "We follow Sersha's trail to the Gear Nave" travelled to the Censer Vault (650).
Fixture m40-r7-typed, no model."""

from aidm.dm.choice_tool import ChooseActionsArgs, choice_tool
from aidm.models.action_menu import ActionMenu, MenuChoice, MenuStep
from aidm.rules.acts import RefusedIntent
from aidm.rules.menu_steps import to_acts
from aidm.rules.menu_unoffered import not_offered, with_unoffered
from tests.ai.chooser_fixtures import FIGHT_SEQ, REGS, TYPED, menu_at, state_at

R7, TRAIL = "m40-r7-typed", 649
BRIENNE = "pc-p2"
NAVE = "the-gear-nave"
LINE = "We follow Sersha's trail to the Gear Nave"


def _menu(text: str, at: tuple[str, int] = (R7, TRAIL), actor: str = BRIENNE) -> ActionMenu:
    return with_unoffered(state_at(*at), menu_at(*at, actor), text)


def test_v1_m40_a_known_place_out_of_reach_is_not_offered() -> None:
    menu = _menu(LINE)
    (nave,) = [t for t in menu.unoffered if t.kind == "place"]
    assert nave.id == NAVE
    assert nave.label == "The Gear Nave (locked until the master of The Sunk Vestry is dealt with)"
    travel = next(e for e in menu.entries if e.id == "travel")
    assert NAVE not in travel.target_ids and "the-censer-vault" in travel.target_ids


def test_v1_m40_a_travel_step_at_it_is_refused_never_a_stand_in() -> None:
    menu = _menu(LINE)
    step = MenuStep(entry="travel", targets=(NAVE,))
    assert not_offered(menu, step) == (NAVE,)
    args = {"steps": [{"do": "travel", "to": [NAVE], "qty": 1}], "other": None, "colour": ""}
    built = choice_tool(menu).args_model.model_validate(args)
    assert isinstance(built, ChooseActionsArgs)
    assert built.to_choice() == MenuChoice(steps=(step,))
    why = "The Gear Nave: locked until the master of The Sunk Vestry is dealt with."
    acts = to_acts(state_at(R7, TRAIL), menu, built.to_choice(), REGS, LINE)
    assert acts == [RefusedIntent(BRIENNE, why)]
    told = to_acts(state_at(R7, TRAIL), menu, MenuChoice(other=True), REGS, LINE)
    assert told == [RefusedIntent(BRIENNE, why)]  # the line as `other` is refused the same


def test_a_place_the_party_never_heard_of_is_never_named() -> None:
    """The Lathe Chantry is a locked tier-3 place no quest or lead names: it stays unknown."""
    menu = _menu("We march on to the Lathe Chantry")
    assert not [t for t in menu.unoffered if t.kind == "place"]


def test_a_place_on_the_map_stays_a_travel_target() -> None:
    menu = _menu("We go to the Censer Vault")
    assert not menu.unoffered
    assert any("the-censer-vault" in e.target_ids for e in menu.entries if e.id == "travel")


def test_a_fight_menu_names_no_place() -> None:
    menu = _menu(LINE, (TYPED, FIGHT_SEQ), "pc-p2")
    assert not [t for t in menu.unoffered if t.kind == "place"]
