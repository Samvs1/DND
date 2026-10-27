"""M40.1 round 7 Z1: the confirm card waiting for a hero's player is part of that hero's menu
(`rules.menu_card`), labelled from the card itself; any other hero's menu has no trace of it.
Real replayed state (fixture m40-r7-typed, the parley card at 383), no model."""

from aidm.dm.chooser import exact_choice
from aidm.models.action_menu import ActionKind, MenuChoice, MenuStep
from aidm.models.protocol_client import CancelHostile, ConfirmHostile
from aidm.rules.menu_card import CARD_NO, CARD_YES, WaitingCard, card_act, with_card
from aidm.rules.menu_steps import step_acts, to_acts
from aidm.session.held import PARLEY_ASK
from tests.ai.chooser_fixtures import FIGHT_SEQ, REGS, TYPED, menu_at, state_at

R7 = "m40-r7-typed"
YES_AT = 383  # "Yes, go ahead, I mean it" with Brienne's parley card up
BRIENNE, ELOWEN = "pc-p2", "pc-p4"
CARD = WaitingCard(BRIENNE, PARLEY_ASK)
ACT = "This answers the fight offer as a parley: one roll, a failure starts the fight"


def test_card_act_is_the_card_without_its_question() -> None:
    assert card_act(PARLEY_ASK) == ACT
    hostile = "Attacking Old Broker Tann is a point of no return: they will fight back. Confirm?"
    assert (
        card_act(hostile)
        == "Attacking Old Broker Tann is a point of no return: they will fight back"
    )


def test_v1_m40_the_card_is_in_its_own_heros_menu() -> None:
    menu = with_card(menu_at(R7, YES_AT, BRIENNE), CARD)
    yes, no = menu.entries[:2]
    assert (yes.id, no.id) == (CARD_YES, CARD_NO)
    assert {yes.kind, no.kind} == {ActionKind.CARD}
    assert ACT in yes.label and "Confirm?" not in yes.label
    assert yes.label.startswith("Yes, do it") and no.label.startswith("No, hold back")
    assert yes.max_targets == 0 and no.max_targets == 0
    assert any(e.id == "offer:fight" for e in menu.entries)  # the offer still waits too


def test_v1_m40_a_card_for_another_seat_is_not_in_this_menu() -> None:
    plain = menu_at(R7, YES_AT, ELOWEN)
    assert with_card(plain, CARD) == plain
    assert not any(e.kind is ActionKind.CARD for e in with_card(plain, CARD).entries)
    assert with_card(plain, None) == plain


def test_a_fight_menu_never_carries_a_card() -> None:
    fight = menu_at(TYPED, FIGHT_SEQ, "pc-p2")
    assert with_card(fight, WaitingCard(fight.actor_id, PARLEY_ASK)) == fight


def test_card_steps_are_the_cards_own_buttons() -> None:
    state = state_at(R7, YES_AT)
    menu = with_card(menu_at(R7, YES_AT, BRIENNE), CARD)
    assert step_acts(state, menu, MenuStep(entry=CARD_YES), REGS) == [ConfirmHostile()]
    assert step_acts(state, menu, MenuStep(entry=CARD_NO), REGS) == [CancelHostile()]
    # a yes ends the line: what the held act does decides what comes next
    both = MenuChoice(steps=(MenuStep(entry=CARD_YES), MenuStep(entry="look")))
    assert to_acts(state, menu, both, REGS) == [ConfirmHostile()]


def test_the_cards_button_words_are_its_exact_answer() -> None:
    """A typed "Yes, do it" is the card's own button string: the exact path, no model call."""
    menu = with_card(menu_at(R7, YES_AT, BRIENNE), CARD)
    assert exact_choice(menu, "Yes, do it") == MenuChoice(steps=(MenuStep(entry=CARD_YES),))
    assert exact_choice(menu, "No, hold back") == MenuChoice(steps=(MenuStep(entry=CARD_NO),))
