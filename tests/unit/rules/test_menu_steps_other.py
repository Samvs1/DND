"""Steps and `other` in one choice (M36.5, DECISIONS M36.5): the off-menu part runs before the
steps when `other_first`, else after them, and never after a step that ended the line."""

from functools import cache

from aidm.data.combat_data import combat_registries
from aidm.models.action_menu import MenuChoice, MenuStep
from aidm.models.commands import AttackCommand, DodgeCommand, EndTurnCommand, MoveCommand
from aidm.models.state import GameState
from aidm.rules.action_menu import build_menu
from aidm.rules.acts import OtherIntent
from aidm.rules.menu_steps import to_acts
from tests.session.playtest_saves import replay_until

REGS = combat_registries()
TYPED, SEQ, HERO = "m35-r6-typed", 435, "pc-p2"  # Brienne's turn, the kobold in the crypt
LINE = "I leap onto the table and drive my longsword into the nearest kobold"
STRIKE = MenuStep(entry="attack:longsword", targets=("kobold-1",))
WALK_AND_STRIKE = [
    [MoveCommand(actor_id=HERO, zone_id="collapsed_vault")],
    AttackCommand(actor_id=HERO, target_id="kobold-1", option="main_hand"),
]


@cache
def _state() -> GameState:
    return replay_until(TYPED, SEQ)


def _acts(choice: MenuChoice) -> list[object]:
    return list(to_acts(_state(), build_menu(_state(), HERO, REGS), choice, REGS, LINE))


def test_menu_steps_other_first_runs_before_the_strike() -> None:
    choice = MenuChoice(
        steps=(STRIKE,), other=True, other_text="leap onto the table", other_first=True
    )
    assert _acts(choice) == [OtherIntent(HERO, "leap onto the table"), *WALK_AND_STRIKE]


def test_menu_steps_other_after_the_strike_and_whole_line_by_default() -> None:
    assert _acts(MenuChoice(steps=(STRIKE,), other=True)) == [
        *WALK_AND_STRIKE,
        OtherIntent(HERO, LINE),
    ]


def test_menu_steps_other_never_after_an_ended_turn() -> None:
    steps = (MenuStep(entry="dodge"), MenuStep(entry="end-turn"))
    assert _acts(MenuChoice(steps=steps, other=True, other_text="whistle")) == [
        DodgeCommand(actor_id=HERO),
        EndTurnCommand(actor_id=HERO),
    ]
